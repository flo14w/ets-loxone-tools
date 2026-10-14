"""ETS XML -> Loxone: explicit template-based, offline import."""
from pathlib import Path
from dataclasses import dataclass
from copy import deepcopy
import re
import uuid
import json
import sys
import os
import tempfile
import unicodedata
from datetime import datetime
import xml.etree.ElementTree as ET


def read_xml(path):
    data = Path(path).read_bytes()
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise ValueError('XML mit DTD/Entities wird nicht unterstützt.')
    return ET.ElementTree(ET.fromstring(data, parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))))


def address(value):
    parts = value.strip().split('/')
    limits = {1: [65535], 2: [31, 2047], 3: [31, 7, 255]}
    if len(parts) not in limits or any(not p.isdecimal() for p in parts):
        raise ValueError('Ungültige Gruppenadresse: ' + value)
    nums = list(map(int, parts))
    if any(n > m for n, m in zip(nums, limits[len(parts)])):
        raise ValueError('Gruppenadresse außerhalb des Bereichs: ' + value)
    n = nums[0] if len(nums) == 1 else (nums[0] << 11) + (nums[1] if len(nums) == 2 else (nums[1] << 8) + nums[2])
    return f'{n >> 11}/{(n >> 8) & 7}/{n & 255}'


@dataclass
class Row:
    name: str
    ga: str
    dpt: str
    group: str
    template: str = ''
    role: str = ''
    type_id: int | None = None
    category_id: str = ''
    room_id: str = ''


def words(value):
    value = unicodedata.normalize('NFKD', value.casefold().replace('ß', 'ss'))
    return re.findall(r'[a-z0-9]+', ''.join(c for c in value if not unicodedata.combining(c)))


# Resource labels in installed Loxone Config, cross-checked against all
# 20 objects in KNX_Typvorlagen.Loxone. Runtime settings come from those profiles.
AUTO_TYPES = {1: (0, 'DPT1 · Schalten'), 3: (1, 'DPT3 · Dimmen'),
              10: (2, 'DPT10 · Zeit'), 11: (3, 'DPT11 · Datum'),
              9: (4, 'DPT9 · 2-Byte-Gleitkomma'),
              7: (9, 'DPT7/8 · 16-Bit-Wert'), 8: (9, 'DPT7/8 · 16-Bit-Wert'),
              12: (10, 'DPT12/13 · 32-Bit-Wert'), 13: (10, 'DPT12/13 · 32-Bit-Wert'),
              6: (13, 'DPT5/6 · 8-Bit-Wert'),
              14: (8, 'DPT14 · 4-Byte-Gleitkomma')}


SUPPORTED_DPTS = {1, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14}
TYPE_LABELS = {0: 'Schalten / Tasten (DPT1)', 1: 'Dimmen EIS2 (DPT3)',
               2: 'Zeit (DPT10)', 3: 'Datum (DPT11)', 4: 'Analogwert (DPT9)',
               5: 'Dimmen / Position 0–100 % (DPT5.001)',
               8: 'Analogwert (DPT14)', 9: '16-Bit-Wert (DPT7/8)',
               10: '32-Bit-Wert (DPT12/13)', 13: '8-Bit-Wert (DPT5/6)'}


def unsupported(dpt):
    mains = re.findall(r'(?:DPST|DPT)-(\d+)(?:-|\b)', dpt)
    return any(int(main) not in SUPPORTED_DPTS for main in mains)


def dpt_type(dpt):
    match = re.fullmatch(r'(?:DPST|DPT)-(\d+)(?:-(\d+))?', dpt.strip())
    if not match:
        return None
    main, sub = int(match[1]), match[2]
    if main == 5 and sub == '1':
        return (5, 'DPT5.001 · Prozent 0–100')
    if main == 5 and sub == '10':
        return (13, 'DPT5/6 · 8-Bit-Wert')
    return AUTO_TYPES.get(main)


def load_ets(path):
    rows = []
    def visit(node, groups):
        tag = node.tag.split('}')[-1] if isinstance(node.tag, str) else ''
        if tag == 'GroupRange':
            groups = groups + [node.get('Name', '')]
        if tag == 'GroupAddress':
            rows.append(Row(node.get('Name', ''), address(node.get('Address', '')), node.get('DPTs', node.get('DatapointType', '')), ' / '.join(groups)))
        for child in node:
            visit(child, groups)
    visit(read_xml(path).getroot(), [])
    if not rows:
        raise ValueError('Keine ETS-Gruppenadressen in der XML-Datei gefunden.')
    return rows


class Project:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.source_bytes = self.path.read_bytes()
        self.tree = read_xml(path)
        self.categories = {e.get('U'): e.get('Title', '') for e in self.tree.iter('C') if e.get('Type') == 'Category' and e.get('U')}
        self.rooms = {e.get('U'): e.get('Title', '') for e in self.tree.iter('C') if e.get('Type') == 'Place' and e.get('U')}
        if self.tree.getroot().tag != 'ControlList':
            raise ValueError('Keine unterstützte Loxone-Datei (ControlList).')
        self.targets = {}
        self.templates = {}
        self.existing = {}
        for ext in self.tree.iter('C'):
            if ext.get('Type') != 'LoxKnx':
                continue
            key = f"{ext.get('Title', 'KNX')} [{ext.get('U')}]"
            self.targets[key] = ext
            known = set()
            for item in ext.iter('C'):
                if item.get('Type') in ('EIBsensor', 'EIBactor'):
                    for ga in re.findall(r'\d+/\d+/\d+', item.get('EibAddr', '')):
                        known.add(address(ga))
                    label = f"{'Sensor' if item.get('Type') == 'EIBsensor' else 'Aktor'} · {item.get('Title')} · EIBType {item.get('EIBType', '0 (Standard)')} · {len(self.templates)+1}"
                    self.templates[label] = item
            self.existing[key] = known
        if not self.targets:
            raise ValueError('Keine KNX Extension gefunden. Diese zuerst in Loxone Config anlegen.')
        if not self.templates:
            raise ValueError('Bitte zuerst KNX-Sensoren/Aktoren als Datentyp-Vorlagen in Loxone Config anlegen.')
        self.auto = {}
        profiles = json.loads((Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / 'type_profiles.json').read_text(encoding='utf-8'))
        for role, kind in [('Sensor', 'EIBsensor'), ('Aktor', 'EIBactor')]:
            base = next((n for n in self.templates.values() if n.get('Type') == kind), None)
            if base is None:
                continue
            for type_id, desc in dict(list(AUTO_TYPES.values()) + [(5, 'DPT5.001 · Prozent 0–100'), (6, 'DPT1 · Jalousie')]).items():
                profile = profiles.get(f'{kind}:{type_id}')
                if not profile:
                    continue
                node = ET.Element('C', profile['attributes'])
                node.set('U', '00000000-0000-0000-ffff000000000000')
                for connector in profile['connectors']:
                    ET.SubElement(node, 'Co', {'K': connector, 'U': '00000000-0000-0000-ffff000000000000'})
                if base.find('IoData') is not None:
                    node.append(deepcopy(base.find('IoData')))
                display = ET.SubElement(node, 'Display', profile['display'])
                display.set('Unit', '<v.m>' if type_id == 2 else '<v.d>' if type_id == 3 else '<v.1> %' if type_id == 5 else '<v>' if type_id in (0, 1, 6, 9, 10, 13) else '<v.2>')
                label = f'{role} · {desc} (automatisch)'
                self.templates[label] = node
                self.auto[(role, type_id)] = label

    def assign_auto(self, row, role):
        if unsupported(row.dpt):
            row.role = row.template = ''
            return
        row.role = role
        typ = dpt_type(row.dpt)
        row.template = self.auto.get((role, typ[0]), '') if typ else ''
        if role == 'Aktor' and row.dpt == 'DPST-1-8':
            row.template = self.auto.get((role, 6), row.template)

    def prepare(self, rows):
        for row in rows:
            typ = dpt_type(row.dpt)
            row.type_id = typ[0] if typ and not unsupported(row.dpt) else None
            row.role = 'Aktor' if row.type_id == 1 else ''
            row.category_id = self.suggest_category(row.group)
            row.room_id = self.suggest_room(row.name)
            self.sync(row)

    def suggest_category(self, group):
        text = ' '.join(words(group))
        rules = {'Beleuchtung': ('beleuchtung', 'licht', 'dimmen', 'dimm'),
                 'Beschattung': ('jalous', 'jalos', 'rollad', 'rolllad', 'rollo', 'beschattung', 'raffstore')}
        matches = {uid for title, terms in rules.items() if any(term in text for term in terms)
                   for uid, name in self.categories.items() if words(name) == words(title)}
        return next(iter(matches)) if len(matches) == 1 else ''

    def suggest_room(self, name):
        tokens = set(words(name))
        candidates = [(len(words(title)), uid) for uid, title in self.rooms.items()
                      if words(title) and set(words(title)) <= tokens and words(title) != ['nicht', 'zugeordnet']]
        if not candidates:
            return ''
        best = max(score for score, _ in candidates)
        matches = [uid for score, uid in candidates if score == best]
        return matches[0] if len(matches) == 1 else ''

    def sync(self, row):
        row.template = self.auto.get((row.role, row.type_id), '') if row.role and not unsupported(row.dpt) else ''

    def set_role(self, row, role):
        if unsupported(row.dpt):
            return
        row.role = 'Aktor' if role and row.type_id == 1 else role
        self.sync(row)

    def set_type(self, row, type_id):
        if not row.role or unsupported(row.dpt) or type_id not in TYPE_LABELS:
            return
        row.type_id = type_id
        if type_id == 1:
            row.role = 'Aktor'
        self.sync(row)

    def name_matches(self, row, target):
        return [item for item in self.targets[target].iter('C')
                if item.get('Type') in ('EIBsensor', 'EIBactor')
                and item.get('Title', '').strip() == row.name.strip()]

    def preview(self, rows, target, update_existing=False):
        ext = self.targets[target]
        seen = set(self.existing[target])
        names = set()
        selected_rows = [row for row in rows if row.template or row.role]
        if update_existing:
            updating = {id(item) for row in selected_rows for item in self.name_matches(row, target)}
            seen = {address(ga) for item in ext.iter('C')
                    if item.get('Type') in ('EIBsensor', 'EIBactor') and id(item) not in updating
                    for ga in re.findall(r'\d+/\d+/\d+', item.get('EibAddr', ''))}
        result = []
        added = 0
        for row in selected_rows:
            if not row.template and not row.role:
                continue
            template = self.templates.get(row.template)
            matches = self.name_matches(row, target) if update_existing else []
            added += not matches
            issue = ''
            if unsupported(row.dpt):
                issue = 'DPT wird von Loxone nicht unterstützt – Import ausgeschlossen'
            elif row.category_id and row.category_id not in self.categories:
                issue = 'Kategorie nicht im aktuellen Projekt vorhanden'
            elif row.room_id and row.room_id not in self.rooms:
                issue = 'Raum nicht im aktuellen Projekt vorhanden'
            elif template is None:
                issue = 'DPT fehlt / nicht automatisch unterstützt – Vorlage wählen'
            elif row.role and template.get('Type') != ('EIBsensor' if row.role == 'Sensor' else 'EIBactor'):
                issue = 'Funktion und Datentyp widersprechen sich'
            elif update_existing and not row.name.strip():
                issue = 'Name fehlt'
            elif update_existing and row.name.strip() in names:
                issue = 'Name mehrfach in der Importauswahl'
            elif len(matches) > 1:
                issue = 'Mehrere KNX-Objekte mit gleichem Namen vorhanden'
            elif matches and matches[0].get('Type') != template.get('Type'):
                issue = 'Vorhandenes Objekt hat andere Funktion (Sensor/Aktor)'
            elif ext.find(f"C[@Type='{template.get('Type')}Caption']") is None:
                issue = 'Zielordner fehlt'
            elif row.ga in seen:
                issue = 'Adresse vorhanden oder doppelt'
            seen.add(row.ga)
            names.add(row.name.strip())
            result.append((row, issue))
        if len(self.existing[target]) + added > 500:
            result = [(row, issue or 'Mehr als 500 Adressen an dieser Extension') for row, issue in result]
        return result

    def render(self, rows, target, update_existing=False):
        plan = self.preview(rows, target, update_existing=update_existing)
        if not plan or any(issue for _, issue in plan):
            raise ValueError('Importübersicht enthält keine Einträge oder ungelöste Konflikte.')
        tree = deepcopy(self.tree)
        ext = next(e for e in tree.iter('C') if e.get('U') == self.targets[target].get('U'))
        for row, _ in plan:
            existing = next((item for item in ext.iter('C')
                             if item.get('Type') in ('EIBsensor', 'EIBactor')
                             and item.get('Title', '').strip() == row.name.strip()), None) if update_existing else None
            node = deepcopy(self.templates[row.template])
            kind = node.get('Type')
            node.set('Title', row.name)
            node.set('EibAddr', row.ga)
            node.set('IName', ('KGI' if kind == 'EIBsensor' else 'KGQ') + row.ga.replace('/', '.'))
            io = node.find('IoData')
            if io is None:
                io = ET.SubElement(node, 'IoData')
            for attr, selected, choices in [('Cr', row.category_id, self.categories), ('Pr', row.room_id, self.rooms)]:
                unassigned = next((uid for uid, title in choices.items() if words(title) == ['nicht', 'zugeordnet']), '')
                value = selected or unassigned
                if value:
                    io.set(attr, value)
                else:
                    io.attrib.pop(attr, None)
            if existing is not None:
                # Keep object/connector identities and all existing links and layout.
                for attr in ('EIBType', 'Signed'):
                    if attr not in node.attrib:
                        existing.attrib.pop(attr, None)
                existing.attrib.update({key: value for key, value in node.attrib.items()
                                        if key not in ('U', 'Title')})
                old_io = existing.find('IoData')
                if old_io is None:
                    old_io = ET.SubElement(existing, 'IoData')
                for attr, selected, choices in [('Cr', row.category_id, self.categories), ('Pr', row.room_id, self.rooms)]:
                    if not selected or words(choices.get(selected, '')) in (['nicht', 'zugeordnet'], ['nicht', 'verwenden']):
                        continue
                    if attr in io.attrib:
                        old_io.set(attr, io.get(attr))
                    else:
                        old_io.attrib.pop(attr, None)
                old_display = existing.find('Display')
                if old_display is not None:
                    existing.remove(old_display)
                if node.find('Display') is not None:
                    existing.append(deepcopy(node.find('Display')))
                continue
            for element in node.iter():
                if 'U' in element.attrib:
                    old = element.get('U')
                    # Preserve Loxone's object/connector suffix and replace identity.
                    raw = uuid.uuid4().hex
                    fresh = f'{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:]}'
                    element.set('U', fresh[:18] + old[18:])
            ext.find(f"C[@Type='{kind}Caption']").append(node)
        document = tree.getroot().find("C[@Type='Document']")
        if document is not None and 'NumO' in document.attrib:
            document.set('NumO', str(len(list(tree.iter('C')))))
        # Exclusive creation prevents accidental replacement, including source aliases.
        data = ET.tostring(tree.getroot(), encoding='utf-8', xml_declaration=True)
        ET.fromstring(data)
        return data, len(plan)

    def export(self, rows, target, destination):
        destination = Path(destination).resolve()
        if destination == self.path:
            raise ValueError('Bitte die Funktion „Importieren in aktuelle Loxone Datei“ verwenden.')
        data, count = self.render(rows, target)
        with destination.open('xb') as output:
            output.write(data)
        return count

    def export_current(self, rows, target):
        data, count = self.render(rows, target, update_existing=True)
        if self.path.read_bytes() != self.source_bytes:
            raise ValueError('Die Loxone-Datei wurde seit dem Laden geändert. Bitte neu laden, damit keine Änderungen verloren gehen.')
        backup = self.path.with_name(self.path.stem + '.backup-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8] + self.path.suffix)
        temporary = None
        try:
            with backup.open('xb') as output:
                output.write(self.source_bytes)
                output.flush()
                os.fsync(output.fileno())
            with tempfile.NamedTemporaryFile(dir=self.path.parent, prefix='.knx-import-', suffix='.tmp', delete=False) as output:
                temporary = Path(output.name)
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
            if self.path.read_bytes() != self.source_bytes:
                raise ValueError('Die Quelldatei wurde während des Imports geändert. Import abgebrochen; Sicherung bleibt erhalten.')
            os.replace(temporary, self.path)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
        # Refresh duplicate detection for subsequent imports in the same session.
        self.__init__(self.path)
        return count, backup
