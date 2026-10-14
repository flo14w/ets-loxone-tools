"""Read-only Loxone extraction and ETS5 group address XML generation."""
from dataclasses import dataclass
from pathlib import Path
import re
from collections import Counter
import xml.etree.ElementTree as ET
from importer import read_xml, address, SUPPORTED_DPTS

NS = 'http://knx.org/xml/ga-export/01'
TYPE_DPTS = {0: ('DPT-1',), 1: ('DPT-3',), 2: ('DPT-10',), 3: ('DPT-11',),
             4: ('DPT-9',), 5: ('DPST-5-1',), 6: ('DPT-1',), 8: ('DPT-14',),
             9: ('DPT-7', 'DPT-8'), 10: ('DPT-12', 'DPT-13'), 13: ('DPT-5', 'DPT-6')}
DPT_CHOICES = ['DPT-1', 'DPT-3', 'DPT-5', 'DPST-5-1', 'DPST-5-10', 'DPT-6', 'DPT-7', 'DPT-8', 'DPT-9', 'DPT-10', 'DPT-11', 'DPT-12', 'DPT-13', 'DPT-14']


def number(ga):
    a, b, c = map(int, address(ga).split('/'))
    return a * 2048 + b * 256 + c


def valid_dpt(value):
    match = re.fullmatch(r'(?:DPT-([1-9]\d*)|DPST-([1-9]\d*)-\d+)', value)
    return bool(match and int(match[1] or match[2]) in SUPPORTED_DPTS)


@dataclass
class ExportRow:
    ga: str
    name: str
    dpt: str
    functions: str
    category: str
    room: str
    source: str
    note: str = ''
    selected: bool = True
    omit_dpt: bool = False
    candidates: tuple = ()
    description: str = ''
    original_ga: str = ''


class ReverseProject:
    def __init__(self, path):
        self.path = Path(path).resolve()
        tree = read_xml(path)
        if tree.getroot().tag != 'ControlList':
            raise ValueError('Keine unterstützte Loxone-Datei (ControlList).')
        categories = {e.get('U'): e.get('Title', '') for e in tree.iter('C') if e.get('Type') == 'Category'}
        rooms = {e.get('U'): e.get('Title', '') for e in tree.iter('C') if e.get('Type') == 'Place'}
        self.skipped, groups = [], {}

        def visit(node, source='KNX'):
            if node.get('Type') == 'LoxKnx':
                source = node.get('Title', 'KNX Extension')
            kind = node.get('Type', '')
            if kind in ('EIBsensor', 'EIBactor'):
                raw = node.get('EibAddr', '').strip()
                try:
                    ga = address(raw)
                    if number(ga) == 0:
                        raise ValueError('0/0/0 ist reserviert')
                except ValueError:
                    self.skipped.append(f"{node.get('Title', kind)}: ungültige/leere oder zusammengesetzte Adresse {raw!r}")
                else:
                    try:
                        candidates = TYPE_DPTS.get(int(node.get('EIBType', '0')), ())
                    except ValueError:
                        candidates = ()
                    io = node.find('IoData')
                    # Only merge identical names at the same address. Distinct names
                    # must remain editable even when the source uses a placeholder GA.
                    key = (node.get('Title', '').strip(), ga)
                    if not key[0]:
                        key = (f'__unnamed_{len(groups)}', ga)
                    groups.setdefault(key, []).append((node.get('Title', ''), candidates,
                        'Sensor' if kind == 'EIBsensor' else 'Aktor',
                        categories.get(io.get('Cr'), '') if io is not None else '',
                        rooms.get(io.get('Pr'), '') if io is not None else '', source))
            elif kind.startswith('EIB') and node.get('EibAddr'):
                self.skipped.append(f"{node.get('Title', kind)}: {kind} wird nicht automatisch ausgewertet ({node.get('EibAddr')}).")
            for child in node:
                visit(child, source)

        visit(tree.getroot())
        self.rows = []
        self.source_count = sum(map(len, groups.values()))
        source_addresses = {}
        for (_, ga), items in groups.items():
            source_addresses.setdefault(ga, []).extend(item[0] or '(Ohne Namen)' for item in items)
        self.source_warnings = [f'WARNUNG – Loxone-Adresse {ga} ist bei {len(names)} Objekten vorhanden:\n  ' + '\n  '.join(names)
                                for ga, names in source_addresses.items() if len(names) > 1]
        for (_, ga), items in sorted(groups.items(), key=lambda item: (number(item[0][1]), item[0][0].casefold())):
            candidate_sets = [set(item[1]) for item in items]
            common = set.intersection(*candidate_sets)
            candidates = tuple(sorted(set.union(*candidate_sets)))
            dpt = next(iter(common)) if len(common) == 1 else ''
            def joined(index):
                return ' / '.join(dict.fromkeys(item[index] for item in items if item[index]))
            notes = []
            if len(items) > 1:
                notes.append(f'{len(items)} Loxone-Objekte zusammengeführt')
            if len({i[0] for i in items}) > 1:
                notes.append('Unterschiedliche Namen – Exportname prüfen')
            if not dpt:
                notes.append('Ursprünglicher Loxone-Typ unklar: ' + (', '.join(candidates) if candidates else 'unbekannter Typ'))
            self.rows.append(ExportRow(ga, items[0][0], dpt, joined(2), joined(3), joined(4), joined(5),
                '; '.join(notes), candidates=candidates,
                description=f'Loxone: {joined(0)}; ursprüngliche Adresse: {ga}; Funktion: {joined(2)}; Kategorie: {joined(3)}; Raum: {joined(4)}; Quelle: {joined(5)}', original_ga=ga))
        self.main_names = {int(r.ga.split('/')[0]): 'Hauptgruppe ' + r.ga.split('/')[0] for r in self.rows}
        self.middle_names = {tuple(map(int, r.ga.split('/')[:2])): 'Mittelgruppe ' + r.ga.split('/')[1] for r in self.rows}

    def ensure_groups(self):
        for row in self.rows:
            main, middle, _ = map(int, address(row.ga).split('/'))
            self.main_names.setdefault(main, f'Hauptgruppe {main}')
            self.middle_names.setdefault((main, middle), f'Mittelgruppe {middle}')

    def read_notes(self):
        targets = {}
        for row in self.rows:
            if row.selected:
                targets.setdefault(address(row.ga), []).append(row.name or '(Ohne Namen)')
        errors = [f'FEHLER – ETS-Zieladresse {ga} ist bei {len(names)} ausgewählten Einträgen doppelt. Vor dem Export neue Adressen vergeben oder Einträge ausschließen:\n  ' + '\n  '.join(names)
                  for ga, names in targets.items() if len(names) > 1]
        return self.skipped + self.source_warnings + errors

    def renumber(self, rows, start, within_group=False):
        next_number = number(start)
        last_number = (next_number // 256) * 256 + 255 if within_group else 65535
        if next_number == 0:
            raise ValueError('Die Startadresse darf nicht 0/0/0 sein.')
        selected = {id(row) for row in rows}
        occupied = {number(row.ga) for row in self.rows if id(row) not in selected}
        assignments = []
        for row in rows:
            while next_number in occupied:
                next_number += 1
            if next_number > last_number:
                raise ValueError('Nicht genügend freie Gruppenadressen im gewählten Bereich. Es wurden keine Adressen geändert.')
            assignments.append((row, address(str(next_number))))
            occupied.add(next_number)
            next_number += 1
        for row, ga in assignments:
            row.ga = ga
        self.ensure_groups()

    def issues(self):
        result = []
        counts = Counter()
        for row in self.rows:
            if row.selected:
                try:
                    counts[address(row.ga)] += 1
                except ValueError:
                    pass
        for row in self.rows:
            if not row.selected:
                continue
            errors = []
            try:
                ga = address(row.ga)
                if number(ga) == 0:
                    errors.append('0/0/0 ist reserviert')
                if counts[ga] > 1:
                    errors.append('ETS-Adresse mehrfach vergeben – neue Adresse zuweisen')
            except ValueError:
                errors.append('Ungültige Adresse')
            if not row.name.strip():
                errors.append('Name fehlt')
            if not row.omit_dpt and row.dpt and not valid_dpt(row.dpt):
                errors.append('Ungültiger DPT – korrigieren oder leer lassen')
            result.append((row, '; '.join(errors)))
        return result

    def render(self):
        plan = self.issues()
        if not plan or any(issue for _, issue in plan):
            raise ValueError('Keine Auswahl oder ungelöste Einträge in der Exportübersicht.')
        # Match the ETS5 export supplied by the user and KNX XML export documentation.
        root = ET.Element('GroupAddress-Export', {'xmlns': NS})
        main_nodes, middle_nodes = {}, {}
        for row, _ in sorted(plan, key=lambda item: number(item[0].ga)):
            ga = address(row.ga)
            main, middle, _ = map(int, ga.split('/'))
            if main not in main_nodes:
                main_nodes[main] = ET.SubElement(root, 'GroupRange', Name=self.main_names.get(main, f'Hauptgruppe {main}'),
                    RangeStart=str(max(1, main * 2048)), RangeEnd=str(main * 2048 + 2047))
            key = (main, middle)
            if key not in middle_nodes:
                start = main * 2048 + middle * 256
                middle_nodes[key] = ET.SubElement(main_nodes[main], 'GroupRange', Name=self.middle_names.get(key, f'Mittelgruppe {middle}'),
                    RangeStart=str(max(1, start)), RangeEnd=str(start + 255))
            attrs = {'Name': row.name.strip(), 'Address': ga, 'Description': row.description}
            if not row.omit_dpt and row.dpt:
                attrs['DPTs'] = row.dpt
            ET.SubElement(middle_nodes[key], 'GroupAddress', attrs)
        ET.indent(root, space='  ')
        return ET.tostring(root, encoding='utf-8', xml_declaration=True)

    def export(self, destination, overwrite=False):
        destination = Path(destination).resolve()
        if destination == self.path:
            raise ValueError('Die Loxone-Quelldatei darf nicht überschrieben werden.')
        data = self.render()
        if overwrite:
            import os
            import tempfile
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=destination.parent, suffix='.tmp', delete=False) as output:
                    temporary = Path(output.name)
                    output.write(data)
                os.replace(temporary, destination)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
        else:
            with destination.open('xb') as output:
                output.write(data)
        return sum(r.selected for r in self.rows)
