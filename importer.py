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
# Runtime settings are loaded from the checked-in type profiles.
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
       …2592 tokens truncated…sys._MEIPASS) / 'assets' / 'loxone-ets-exporter-logo-v1.png' if getattr(sys, 'frozen', False) else BASE / 'output/logo/loxone-ets-exporter-logo-v1.png'
        raw = tk.PhotoImage(file=str(logo))
        factor = max(1, (max(raw.width(), raw.height()) + 63) // 64)
        self.logo = raw.subsample(factor, factor)
        self.iconphoto(True, self.logo)
        tk.Label(banner, image=self.logo, background='#293944').pack(side='left', padx=(0, 12))
        tk.Label(banner, text='LOXONE  →  ETS', font=('Segoe UI', 22, 'bold'), background='#293944', foreground='white').pack(side='left')
        tk.Label(banner, text='GRUPPENADRESSEN ALS ETS-XML EXPORTIEREN', background='#293944', foreground='#b1d9f5').pack(side='right')
        tk.Frame(self, background=BLUE, height=4).pack(fill='x')
        files = ttk.Frame(self, padding=16)
        files.pack(fill='x')
        ttk.Label(files, text='Loxone-Datei').pack(side='left')
        ttk.Entry(files, textvariable=self.path).pack(side='left', fill='x', expand=True, padx=10)
        ttk.Button(files, text='Auswählen …', command=self.pick).pack(side='left')
        ttk.Button(files, text='Adressen einlesen', style='Accent.TButton', command=self.load).pack(side='left', padx=(8, 0))
        controls = ttk.Frame(self, padding=(16, 0))
        controls.pack(fill='x')
        ttk.Button(controls, text='Markierte exportieren', command=lambda: self.select(True)).pack(side='left')
        ttk.Button(controls, text='Markierte ausschließen', command=lambda: self.select(False)).pack(side='left', padx=8)
        ttk.Button(controls, text='Bearbeiten …', command=self.edit).pack(side='left')
        ttk.Button(controls, text='Adressen vergeben …', command=self.renumber).pack(side='left', padx=8)
        ttk.Button(controls, text='Gruppennamen …', command=self.group_names).pack(side='right')
        ttk.Label(self, text='1  Auswahl und Datentypen prüfen    →    2  Exportübersicht    →    3  XML in ETS importieren\nSpaltenkopf: Filter · Doppelklick: Eintrag bearbeiten · Die Loxone-Datei wird nur gelesen.', padding=16).pack(anchor='w')
        footer = ttk.Frame(self, padding=16)
        footer.pack(side='bottom', fill='x')
        ttk.Label(footer, textvariable=self.status).pack(anchor='w', pady=(0, 8))
        ttk.Button(footer, text='Sichtbare markieren', command=lambda: self.table.mark_all()).pack(side='left')
        ttk.Button(footer, text='Filter zurücksetzen', command=lambda: self.table.reset()).pack(side='left', padx=8)
        ttk.Button(footer, text='Lesehinweise …', command=self.notes).pack(side='left')
        ttk.Button(footer, text='Weiter: Exportübersicht →', style='Accent.TButton', command=self.review).pack(side='right')
        self.table = FilterTable(self, ('Export', 'ETS-Adresse', 'Loxone-Adresse', 'Name', 'ETS-DPT', 'Funktion', 'Kategorie', 'Raum', 'Quelle', 'Prüfung'), (75, 110, 120, 240, 130, 120, 160, 160, 180, 330))
        self.table.pack(fill='both', expand=True, padx=16)
        self.table.tree.bind('<Double-1>', lambda e: self.edit() if self.table.tree.identify_region(e.x, e.y) in ('cell', 'tree') else None)
        files = list(BASE.glob('*.Loxone')) or list(BASE.parent.glob('*.Loxone'))
        files.sort(key=lambda p: ('.backup-' in p.name.casefold(), 'typvorlagen' in p.name.casefold(), p.name.casefold()))
        if files:
            self.path.set(str(files[0]))

    def pick(self):
        chosen = filedialog.askopenfilename(**dialog_location(self.path.get()), filetypes=[('Loxone Config', '*.Loxone')])
        if chosen:
            self.path.set(chosen)

    def load(self):
        if self.project and not messagebox.askyesno('Neu laden', 'Aktuelle Exportauswahl und Änderungen verwerfen?'):
            return
        try:
            self.project = ReverseProject(self.path.get())
            self.table.filters.clear()
            self.refresh()
        except Exception as exc:
            messagebox.showerror('Einlesen fehlgeschlagen', str(exc))

    def refresh(self):
        if not self.project:
            return
        issues = {id(row): issue for row, issue in self.project.issues()}
        self.table.set_data([(i, ('Ja' if r.selected else 'Nein', r.ga, r.original_ga, r.name, 'Ohne DPT' if r.omit_dpt or not r.dpt else r.dpt, r.functions, r.category, r.room, r.source, issues.get(id(r)) or r.note or 'Bereit'), ('warning',) if issues.get(id(r)) else ()) for i, r in enumerate(self.project.rows)])
        chosen = sum(r.selected for r in self.project.rows)
        errors = sum(bool(issue) for issue in issues.values())
        self.status.set(f'{self.project.source_count} KNX-Objekte · {len(self.project.rows)} Einträge nach Name/Adresse · {chosen} ausgewählt · {errors} zu klären · {len(self.project.read_notes())} Lesehinweise')

    def select(self, selected):
        if self.project:
            for iid in self.table.tree.selection():
                self.project.rows[int(iid)].selected = selected
            self.refresh()

    def notes(self):
        if self.project:
            win = tk.Toplevel(self)
            win.title('Lesehinweise')
            win.geometry('850x400')
            frame = ttk.Frame(win, padding=16)
            frame.pack(fill='both', expand=True)
            text = tk.Text(frame, wrap='word', font=('Segoe UI', 10))
            scroll = ttk.Scrollbar(frame, command=text.yview)
            text.configure(yscrollcommand=scroll.set)
            scroll.pack(side='right', fill='y')
            text.pack(side='left', fill='both', expand=True)
            text.insert('1.0', '\n\n'.join(self.project.read_notes()) or 'Keine Lesehinweise oder Adresskonflikte vorhanden.')
            text.configure(state='disabled')

    def edit(self):
        if not self.project or not self.table.tree.selection():
            return
        rows = [self.project.rows[int(i)] for i in self.table.tree.selection()]
        win = tk.Toplevel(self)
        win.title('Exportdaten bearbeiten')
        win.geometry('700x450')
        win.minsize(650, 450)
        win.transient(self)
        win.grab_set()
        box = ttk.Frame(win, padding=18)
        box.pack(fill='both', expand=True)
        name = tk.StringVar(value=rows[0].name if len(rows) == 1 else '')
        ga = tk.StringVar(value=rows[0].ga if len(rows) == 1 else '')
        dpt = tk.StringVar(value=rows[0].dpt if len({r.dpt for r in rows}) == 1 else '')
        omit = tk.BooleanVar(value=all(r.omit_dpt for r in rows))
        ttk.Label(box, text=f'{len(rows)} Adresse(n) bearbeiten', font=('Segoe UI', 15, 'bold')).pack(anchor='w')
        ttk.Label(box, text='Name (nur bei einer einzelnen Adresse änderbar)').pack(anchor='w', pady=(12, 0))
        ttk.Entry(box, textvariable=name, state='normal' if len(rows) == 1 else 'disabled').pack(fill='x')
        ttk.Label(box, text='ETS-Adresse (einzeln; für mehrere Einträge „Adressen vergeben“ nutzen)').pack(anchor='w', pady=(12, 0))
        ttk.Entry(box, textvariable=ga, state='normal' if len(rows) == 1 else 'disabled').pack(fill='x')
        ttk.Label(box, text='ETS-DPT, z. B. DPT-9 oder DPST-9-1 (9.001); leer = ohne DPT').pack(anchor='w', pady=(12, 0))
        ttk.Combobox(box, textvariable=dpt, values=DPT_CHOICES).pack(fill='x')
        ttk.Checkbutton(box, text='Ausdrücklich ohne Datentyp exportieren (in ETS später festlegen)', variable=omit).pack(anchor='w', pady=10)
        ttk.Label(box, text='Loxone speichert bei einigen Typen nur die Datenbreite, nicht den genauen KNX-DPT.', wraplength=640).pack(anchor='w')

        def apply():
            from reverse_importer import valid_dpt
            if not omit.get() and dpt.get().strip() and not valid_dpt(dpt.get().strip()):
                messagebox.showerror('Datentyp', 'Bitte einen gültigen DPT in der angegebenen Schreibweise wählen.', parent=win)
                return
            if len(rows) == 1:
                try:
                    new_ga = address(ga.get())
                    if number(new_ga) == 0:
                        raise ValueError('0/0/0 ist reserviert.')
                except ValueError as exc:
                    messagebox.showerror('Gruppenadresse', str(exc), parent=win)
                    return
            for row in rows:
                if len(rows) == 1:
                    row.name = name.get().strip()
                    row.ga = new_ga
                row.dpt, row.omit_dpt = dpt.get().strip(), omit.get()
            self.project.ensure_groups()
            self.refresh()
            win.destroy()

        ttk.Button(box, text='Übernehmen', style='Accent.TButton', command=apply).pack(side='bottom', anchor='e')

    def renumber(self):
        if not self.project or not self.table.tree.selection():
            return
        ids = set(self.table.tree.selection())
        rows = [self.project.rows[int(i)] for i in self.table.tree.get_children() if i in ids]
        win = tk.Toplevel(self)
        win.title('ETS-Adressen fortlaufend vergeben')
        win.geometry('650x340')
        win.minsize(650, 340)
        win.transient(self)
        win.grab_set()
        box = ttk.Frame(win, padding=18)
        box.pack(fill='both', expand=True)
        ttk.Label(box, text=f'{len(rows)} markierte Einträge neu adressieren', font=('Segoe UI', 14, 'bold')).pack(anchor='w')
        main, middle, _ = rows[0].ga.split('/')
        values = [tk.StringVar(value=main), tk.StringVar(value=middle), tk.StringVar(value='1')]
        fields = ttk.Frame(box)
        fields.pack(fill='x', pady=12)
        for column, (label, maximum, value) in enumerate(zip(
                ('Hauptgruppe (0–31)', 'Mittelgruppe (0–7)', 'Start-Untergruppe (0–255)'),
                (31, 7, 255), values)):
            ttk.Label(fields, text=label).grid(row=0, column=column, sticky='w', padx=6)
            ttk.Spinbox(fields, from_=0, to=maximum, textvariable=value, width=18).grid(row=1, column=column, sticky='ew', padx=6)
            fields.columnconfigure(column, weight=1)
        ttk.Label(box, text='Vergabe aufsteigend in Tabellenreihenfolge, nur innerhalb der gewählten Haupt- und Mittelgruppe. Belegte Adressen anderer Einträge werden übersprungen.\nDie Loxone-Datei wird nicht geändert; neue ETS-Adressen sind dort separat abzugleichen.', wraplength=600).pack(anchor='w', pady=12)

        def apply():
            try:
                parts = [value.get().strip() for value in values]
                if any(not part.isascii() or not part.isdigit() for part in parts) or any(int(part) > limit for part, limit in zip(parts, (31, 7, 255))):
                    raise ValueError('Bitte Hauptgruppe 0–31, Mittelgruppe 0–7 und Start-Untergruppe 0–255 eingeben.')
                self.project.renumber(rows, '/'.join(parts), within_group=True)
                self.refresh()
                win.destroy()
            except ValueError as exc:
                messagebox.showerror('Adressvergabe', str(exc), parent=win)

        ttk.Button(box, text='Adressen zuweisen', style='Accent.TButton', command=apply).pack(side='bottom', anchor='e')

    def group_names(self):
        if not self.project:
            return
        win = tk.Toplevel(self)
        win.title('ETS-Haupt- und Mittelgruppen benennen')
        win.geometry('750x550')
        win.minsize(650, 420)
        win.transient(self)
        win.grab_set()
        ttk.Label(win, text='Namen direkt anklicken und bearbeiten · Enter: übernehmen · Esc: verwerfen', padding=16).pack(anchor='w')
        foot = ttk.Frame(win, padding=16)
        foot.pack(side='bottom', fill='x')
        tree = ttk.Treeview(win, columns=('Bereich', 'Name'), show='headings')
        tree.heading('Bereich', text='Bereich')
        tree.heading('Name', text='Name in ETS')
        tree.pack(fill='both', expand=True, padx=16)
        records = []
        for key, title in self.project.main_names.items():
            records.append((self.project.main_names, key, f'{key}/*/*', title))
            records.extend((self.project.middle_names, pair, f'{pair[0]}/{pair[1]}/*', text) for pair, text in self.project.middle_names.items() if pair[0] == key)
        for i, (_, _, label, title) in enumerate(records):
            tree.insert('', 'end', iid=str(i), values=(label, title))
        editor = None
        editing_iid = None

        def finish(save=True):
            nonlocal editor, editing_iid
            if editor is not None:
                entry, iid = editor, editing_iid
                editor, editing_iid = None, None
                name = entry.get().strip()
                if save and name:
                    mapping, key, _, _ = records[int(iid)]
                    mapping[key] = name
                    tree.set(iid, 'Name', name)
                entry.destroy()
            return 'break'

        def edit_cell(event):
            nonlocal editor, editing_iid
            finish()
            iid = tree.identify_row(event.y)
            if not iid or tree.identify_column(event.x) != '#2':
                return
            bounds = tree.bbox(iid, 'Name')
            if not bounds:
                return
            tree.selection_set(iid)
            tree.focus(iid)
            editing_iid = iid
            editor = ttk.Entry(tree)
            editor.insert(0, tree.set(iid, 'Name'))
            editor.place(x=bounds[0], y=bounds[1], width=bounds[2], height=bounds[3])
            editor.focus_set()
            editor.selection_range(0, 'end')
            editor.bind('<Return>', lambda _: finish())
            editor.bind('<Escape>', lambda _: finish(False))
            editor.bind('<FocusOut>', lambda _: finish())
            return 'break'

        def close():
            finish()
            win.destroy()

        tree.bind('<Button-1>', edit_cell)
        tree.bind('<Configure>', lambda _: finish())
        tree.bind('<MouseWheel>', lambda _: finish())
        win.protocol('WM_DELETE_WINDOW', close)
        ttk.Button(foot, text='Fertig', command=close).pack(side='right')

    def review(self):
        if not self.project:
            return
        plan = self.project.issues()
        if not plan:
            messagebox.showinfo('Keine Auswahl', 'Bitte mindestens eine Adresse für den Export auswählen.')
            return
        win = tk.Toplevel(self)
        win.title('Loxone → ETS · Exportübersicht · v' + VERSION)
        win.geometry('1200x650')
        win.minsize(1000, 550)
        win.transient(self)
        win.grab_set()
        errors = sum(bool(issue) for _, issue in plan)
        missing = sum(r.omit_dpt or not r.dpt for r, _ in plan)
        ttk.Label(win, text=f'{len(plan)} Gruppenadressen · {errors} Fehler · {missing} ohne DPT', font=('Segoe UI', 16, 'bold'), padding=16).pack(anchor='w')
        ttk.Label(win, text='Exportiert wird eine ETS-Gruppenadressen-XML. Es werden keine Geräte- oder Kommunikationsobjekt-Verknüpfungen erstellt.', padding=(16, 0)).pack(anchor='w')
        foot = ttk.Frame(win, padding=16)
        foot.pack(side='bottom', fill='x')
        verified = tk.BooleanVar(value=False)
        button = ttk.Button(foot, text='ETS-XML erstellen …', style='Accent.TButton', state='disabled', command=lambda: self.save(win))
        button.pack(side='right')
        ttk.Button(foot, text='← Zurück', command=win.destroy).pack(side='left')
        ttk.Checkbutton(foot, text='Auswahl, Namen und Datentypen geprüft', variable=verified, command=lambda: button.configure(state='normal' if verified.get() and not errors else 'disabled')).pack(side='left', padx=16)
        table = FilterTable(win, ('Adresse', 'Name', 'ETS-DPT', 'Hauptgruppe', 'Mittelgruppe', 'Prüfung'), (100, 270, 130, 190, 190, 310))
        table.pack(fill='both', expand=True, padx=16, pady=12)
        table.set_data([(i, (r.ga, r.name, 'Ohne DPT' if r.omit_dpt or not r.dpt else r.dpt, self.project.main_names[int(r.ga.split('/')[0])], self.project.middle_names[tuple(map(int, r.ga.split('/')[:2]))], issue or ('Bereit – ohne DPT' if r.omit_dpt or not r.dpt else 'Bereit')), ('warning',) if issue else ()) for i, (r, issue) in enumerate(plan)])

    def save(self, win):
        path = filedialog.asksaveasfilename(parent=win, **dialog_location(str(self.project.path)), initialfile=self.project.path.stem + '_ETS_Gruppenadressen.xml', defaultextension='.xml', filetypes=[('ETS-Gruppenadressen XML', '*.xml')])
        if path:
            try:
                count = self.project.export(path)
                messagebox.showinfo('Export abgeschlossen', f'{count} Gruppenadressen gespeichert:\n{path}\n\nIn ETS: Gruppenadressen → Rechtsklick → Gruppenadressen importieren.', parent=win)
                win.destroy()
            except Exception as exc:
                messagebox.showerror('Export fehlgeschlagen', str(exc), parent=win)


if __name__ == '__main__':
    ReverseApp().mainloop()
