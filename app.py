import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from importer import Project, load_ets, unsupported, TYPE_LABELS
from version import VERSION

BASE = Path(sys.executable if getattr(sys, 'frozen', False) else __file__).resolve().parent
GREEN, BG, INK = '#69b329', '#f1f2f3', '#33383c'


def dialog_location(value):
    path = Path(value).expanduser() if value else BASE
    directory = path if path.is_dir() else path.parent
    while not directory.is_dir() and directory != directory.parent:
        directory = directory.parent
    return {'initialdir': str(directory.resolve())}


class FilterTable(ttk.Frame):
    def __init__(self, parent, columns, widths):
        super().__init__(parent)
        self.columns, self.data, self.filters = columns, [], {}
        self.tree = ttk.Treeview(self, columns=columns, show='headings', selectmode='extended')
        self.tree.bind('<Control-a>', self.mark_all)
        self.tree.bind('<Control-A>', self.mark_all)
        for col, width in zip(columns, widths):
            self.tree.heading(col, text=col + ' ▾', command=lambda c=col: self.filter_dialog(c))
            self.tree.column(col, width=width, minwidth=80)
        self.tree.tag_configure('blocked', foreground='#8b8f93')
        self.tree.tag_configure('warning', foreground='#a25b00')
        self.tree.tag_configure('odd', background='#f3f6f0')
        vs = ttk.Scrollbar(self, orient='vertical', command=self.tree.yview)
        hs = ttk.Scrollbar(self, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        vs.grid(row=0, column=1, sticky='ns')
        hs.grid(row=1, column=0, sticky='ew')
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

    def set_data(self, data):
        self.data = data
        self.refresh()

    def refresh(self):
        selected = set(self.tree.selection())
        self.tree.delete(*self.tree.get_children())
        for iid, values, tags in self.data:
            if all(values[self.columns.index(c)] in allowed for c, allowed in self.filters.items()):
                self.tree.insert('', 'end', iid=str(iid), values=values, tags=tags)
        self.tree.selection_set(list(selected & set(self.tree.get_children())))
        for col in self.columns:
            self.tree.heading(col, text=col + (' ●' if col in self.filters else ' ▾'))

    def reset(self):
        self.filters.clear()
        self.refresh()

    def mark_all(self, event=None):
        self.tree.selection_set(self.tree.get_children())
        return 'break'

    def filter_dialog(self, col):
        index = self.columns.index(col)
        values = sorted({v[index] for _, v, _ in self.data}, key=str.casefold)
        chosen = set(self.filters.get(col, values))
        previous_grab = self.grab_current()
        win = tk.Toplevel(self)
        win.title('Filter · ' + col)
        win.geometry('480x500')
        win.transient(self.winfo_toplevel())
        win.grab_set()
        box = ttk.Frame(win, padding=16)
        box.pack(fill='both', expand=True)
        ttk.Label(box, text=col, font=('Segoe UI', 14, 'bold')).pack(anchor='w')
        ttk.Label(box, text='Werte anklicken, um sie ein- oder auszublenden.').pack(anchor='w', pady=8)
        search = tk.StringVar()
        ttk.Entry(box, textvariable=search).pack(fill='x')
        middle = ttk.Frame(box)
        middle.pack(fill='both', expand=True, pady=8)
        listing = tk.Listbox(middle, selectmode='multiple', exportselection=False, activestyle='none', font=('Segoe UI', 10), selectbackground=GREEN)
        scroll = ttk.Scrollbar(middle, command=listing.yview)
        listing.configure(yscrollcommand=scroll.set)
        listing.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        shown = []

        def close():
            win.destroy()
            if previous_grab is not None and previous_grab.winfo_exists():
                previous_grab.grab_set()

        win.protocol('WM_DELETE_WINDOW', close)

        def remember():
            chosen.difference_update(shown)
            chosen.update(shown[i] for i in listing.curselection())

        def redraw(*_):
            remember()
            shown[:] = [v for v in values if search.get().casefold() in v.casefold()]
            listing.delete(0, 'end')
            for i, value in enumerate(shown):
                listing.insert('end', value or '(Leer)')
                if value in chosen:
                    listing.selection_set(i)

        def apply():
            remember()
            if chosen == set(values):
                self.filters.pop(col, None)
            else:
                self.filters[col] = chosen
            self.refresh()
            close()

        actions = ttk.Frame(box)
        actions.pack(fill='x')
        ttk.Button(actions, text='Alle sichtbaren', command=lambda: listing.selection_set(0, 'end')).pack(side='left')
        ttk.Button(actions, text='Keine sichtbaren', command=lambda: listing.selection_clear(0, 'end')).pack(side='left', padx=5)
        ttk.Button(box, text='Filter anwenden', style='Accent.TButton', command=apply).pack(anchor='e', pady=(12, 0))
        search.trace_add('write', redraw)
        redraw()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f'ETS → Loxone · v{VERSION}')
        self.geometry('1380x860')
        self.minsize(1100, 720)
        self.configure(background=BG)
        self.rows, self.project = [], None
        self.ets, self.lox, self.target = [tk.StringVar() for _ in range(3)]
        self.function = tk.StringVar(value='Sensor')
        self.status = tk.StringVar(value='ETS-Export und Loxone-Projekt laden.')
        self.type_vars, self.role_tables = {}, {}
        self.allocation_widgets = []
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('.', font=('Segoe UI', 10), background=BG, foreground=INK)
        style.configure('TButton', padding=(12, 7))
        style.configure('Accent.TButton', background=GREEN, foreground='white', font=('Segoe UI', 10, 'bold'))
        style.map('Accent.TButton', background=[('active', '#559624'), ('disabled', '#bdcbb4')])
        style.configure('Treeview', rowheight=29, background='white', fieldbackground='white', borderwidth=0)
        style.map('Treeview', background=[('selected', '#d9ebcb')], foreground=[('selected', '#243b18')])
        style.configure('Treeview.Heading', background='#e1e4e6', font=('Segoe UI', 10, 'bold'), padding=(6, 9))
        style.configure('TNotebook.Tab', padding=(22, 10))
        style.map('TNotebook.Tab', background=[('selected', 'white')], foreground=[('selected', '#4c8c20')])
        banner = tk.Frame(self, background='#353a3e', padx=20, pady=14)
        banner.pack(fill='x')
        logo_path = (Path(sys._MEIPASS) / 'assets' / 'ets-loxone-logo-v1.png') if getattr(sys, 'frozen', False) else BASE / 'output' / 'logo' / 'ets-loxone-logo-v1.png'
        original_logo = tk.PhotoImage(file=str(logo_path))
        factor = max(1, (max(original_logo.width(), original_logo.height()) + 63) // 64)
        self.logo = original_logo.subsample(factor, factor)
        self.iconphoto(True, self.logo)
        tk.Label(banner, image=self.logo, background='#353a3e').pack(side='left', padx=(0, 12))
        tk.Label(banner, text='ETS  →  LOXONE', font=('Segoe UI', 21, 'bold'), foreground='white', background='#353a3e').pack(side='left')
        tk.Label(banner, text='KNX GRUPPENADRESSEN IMPORTIEREN', font=('Segoe UI', 10), foreground='#b9dca3', background='#353a3e').pack(side='right')
        tk.Frame(self, background=GREEN, height=4).pack(fill='x')
        files = ttk.Frame(self, padding=(16, 10))
        files.pack(fill='x')
        for i, (label, var, ext) in enumerate([('ETS-Export', self.ets, '*.xml'), ('Loxone-Projekt', self.lox, '*.Loxone')]):
            ttk.Label(files, text=label, width=16).grid(row=i, column=0, sticky='w', pady=3)
            ttk.Entry(files, textvariable=var).grid(row=i, column=1, sticky='ew', padx=8)
            ttk.Button(files, text='Auswählen …', command=lambda v=var, e=ext: self.pick(v, e)).grid(row=i, column=2)
        ttk.Label(files, text='Ziel-Extension').grid(row=2, column=0, sticky='w', pady=4)
        self.targets = ttk.Combobox(files, textvariable=self.target, state='readonly')
        self.targets.grid(row=2, column=1, sticky='ew', padx=8)
        ttk.Button(files, text='Dateien laden', style='Accent.TButton', command=self.load).grid(row=2, column=2, pady=4)
        files.columnconfigure(1, weight=1)
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill='both', expand=True, padx=16)
        overview = ttk.Frame(self.tabs, padding=12)
        types = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(overview, text='1   Funktionen zuordnen')
        self.tabs.add(types, text='2   Datentypen prüfen', state='disabled')
        self.types_page = types
        bar = ttk.Frame(overview)
        bar.pack(fill='x', pady=(0, 10))
        ttk.Label(bar, text='Funktion für markierte Adressen:').pack(side='left')
        ttk.Combobox(bar, textvariable=self.function, values=['Sensor', 'Aktor', 'Nicht importieren'], state='readonly', width=19).pack(side='left', padx=8)
        ttk.Button(bar, text='Funktion übernehmen', command=self.assign_function).pack(side='left')
        ttk.Button(bar, text='Weiter: Datentypen →', style='Accent.TButton', command=lambda: self.tabs.select(types) if self.project else None).pack(side='right')
        ttk.Label(overview, text='Spaltenkopf anklicken zum Filtern · Filter werden kombiniert · Dimmen EIS2 (DPT3) wird automatisch als Aktor eingeordnet.').pack(anchor='w', pady=(0, 8))
        self.overview = FilterTable(overview, ('Adresse', 'Name', 'ETS-DPT', 'Gruppe', 'Funktion', 'Status'), (100, 290, 125, 290, 120, 230))
        self.overview.pack(fill='both', expand=True)
        self.table_actions(overview, self.overview)
        self.role_tabs = ttk.Notebook(types)
        self.role_tabs.pack(fill='both', expand=True)
        for role in ('Sensor', 'Aktor'):
            page = ttk.Frame(self.role_tabs, padding=10)
            self.role_tabs.add(page, text='Sensoren' if role == 'Sensor' else 'Aktoren')
            controls = ttk.Frame(page)
            controls.pack(fill='x', pady=(0, 8))
            ttk.Label(controls, text='Datentyp für markierte Adressen:').pack(side='left')
            var = tk.StringVar(value=TYPE_LABELS[0])
            self.type_vars[role] = var
            labels = [v for k, v in TYPE_LABELS.items() if role == 'Aktor' or k != 1]
            ttk.Combobox(controls, textvariable=var, values=labels, state='readonly', width=41).pack(side='left', padx=8)
            ttk.Button(controls, text='Typ übernehmen', command=lambda r=role: self.assign_type(r)).pack(side='left')
            ttk.Label(page, text='Typ aus ETS-DPT voreingestellt · Mehrfachauswahl mit Strg/Shift oder „Sichtbare markieren“.').pack(anchor='w', pady=(0, 8))
            table = FilterTable(page, ('Adresse', 'Name', 'ETS-DPT', 'Gruppe', 'Funktion', 'Loxone-Typ', 'Kategorie', 'Raum', 'Status'), (90, 230, 110, 200, 90, 280, 170, 170, 180))
            table.pack(fill='both', expand=True)
            self.allocation_controls(page, table, self.refresh)
            table.tree.bind('<<TreeviewSelect>>', lambda _, r=role: self.select_type(r))
            self.role_tables[role] = table
            self.table_actions(page, table)
        foot = ttk.Frame(types)
        foot.pack(side='bottom', before=self.role_tabs, fill='x', pady=(8, 0))
        ttk.Button(foot, text='← Funktionen', command=lambda: self.tabs.select(overview)).pack(side='left')
        ttk.Button(foot, text='Weiter: Importübersicht →', style='Accent.TButton', command=self.review).pack(side='right')
        ttk.Label(self, textvariable=self.status, padding=(18, 12)).pack(side='bottom', before=self.tabs, fill='x')
        for glob, var in [('*.xml', self.ets), ('*.Loxone', self.lox)]:
            matches = list(BASE.glob(glob)) or list(BASE.parent.glob(glob))
            matches.sort(key=lambda p: ('.backup-' in p.name.casefold(), 'typvorlagen' in p.name.casefold(), p.name.casefold()))
            if matches:
                var.set(str(matches[0]))

    def table_actions(self, parent, table):
        bar = ttk.Frame(parent)
        bar.pack(side='bottom', before=table, fill='x', pady=(8, 0))
        ttk.Button(bar, text='Sichtbare markieren', command=table.mark_all).pack(side='left')
        ttk.Button(bar, text='Alle Filter zurücksetzen', command=table.reset).pack(side='left', padx=8)

    def allocation_controls(self, parent, table, changed):
        bar = ttk.Frame(parent)
        bar.pack(before=table, fill='x', pady=(0, 8))
        category, room = tk.StringVar(value='Unverändert'), tk.StringVar(value='Unverändert')
        ttk.Label(bar, text='Kategorie:').grid(row=0, column=0, sticky='w')
        cat_box = ttk.Combobox(bar, textvariable=category, state='readonly', width=25)
        cat_box.grid(row=0, column=1, sticky='ew', padx=8)
        ttk.Label(bar, text='Raum:').grid(row=0, column=2, sticky='w')
        room_box = ttk.Combobox(bar, textvariable=room, state='readonly', width=25)
        room_box.grid(row=0, column=3, sticky='ew', padx=8)
        bar.columnconfigure(1, weight=1)
        bar.columnconfigure(3, weight=1)

        def apply():
            if not self.project:
                return
            cats, rooms = self.allocation_options(self.project.categories), self.allocation_options(self.project.rooms)
            for iid in table.tree.selection():
                row = self.rows[int(iid)]
                if category.get() in cats:
                    row.category_id = cats[category.get()]
                if room.get() in rooms:
                    row.room_id = rooms[room.get()]
            changed()

        ttk.Button(bar, text='Markierten zuweisen', command=apply).grid(row=0, column=4)
        self.allocation_widgets.append((cat_box, room_box, category, room))
        self.update_allocation_options()

    @staticmethod
    def allocation_options(choices):
        options = {'Keine Zuordnung': ''}
        for uid, title in choices.items():
            label = title if list(choices.values()).count(title) == 1 else f'{title} [{uid}]'
            options[label] = uid
        return options

    def update_allocation_options(self):
        for cat_box, room_box, category, room in self.allocation_widgets:
            if not cat_box.winfo_exists():
                continue
            cat_box['values'] = ['Unverändert', *self.allocation_options(self.project.categories if self.project else {})]
            room_box['values'] = ['Unverändert', *self.allocation_options(self.project.rooms if self.project else {})]

    def pick(self, var, extension):
        path = filedialog.askopenfilename(**dialog_location(var.get()), filetypes=[('Projektdatei', extension), ('Alle Dateien', '*.*')])
        if path:
            var.set(path)

    def load(self):
        if any(r.role for r in self.rows) and not messagebox.askyesno('Dateien neu laden', 'Die aktuellen Zuordnungen verwerfen und Dateien neu laden?'):
            return
        try:
            rows, project = load_ets(self.ets.get()), Project(self.lox.get())
            project.prepare(rows)
            self.rows, self.project = rows, project
            self.targets['values'] = list(project.targets)
            self.target.set(next(iter(project.targets)))
            self.update_allocation_options()
            for table in [self.overview, *self.role_tables.values()]:
                table.filters.clear()
            self.tabs.tab(self.types_page, state='normal')
            self.refresh()
        except Exception as exc:
            messagebox.showerror('Laden fehlgeschlagen', str(exc))

    def row_status(self, row):
        if unsupported(row.dpt):
            return 'Nicht unterstützt'
        if not row.role:
            return 'Funktion wählen'
        if not row.template:
            return 'Datentyp wählen'
        return 'Bereit'

    def refresh(self):
        all_data, role_data = [], {'Sensor': [], 'Aktor': []}
        for i, row in enumerate(self.rows):
            status = self.row_status(row)
            base = (row.ga, row.name, row.dpt or 'Fehlt', row.group, row.role or 'Nicht zugeordnet')
            tags = ('blocked',) if unsupported(row.dpt) else ('warning',) if status == 'Datentyp wählen' else ('odd',) if i % 2 else ()
            all_data.append((i, base + (status,), tags))
            if row.role in role_data:
                role_data[row.role].append((i, base + (TYPE_LABELS.get(row.type_id, 'Bitte auswählen'), self.project.categories.get(row.category_id, 'Nicht zugeordnet'), self.project.rooms.get(row.room_id, 'Nicht zugeordnet'), status), tags))
        self.overview.set_data(all_data)
        for i, (role, data) in enumerate(role_data.items()):
            self.role_tables[role].set_data(data)
            self.role_tabs.tab(i, text=f'{"Sensoren" if role == "Sensor" else "Aktoren"} ({len(data)})')
        self.status.set(f'{len(self.rows)} Adressen  ·  {len(role_data["Sensor"])} Sensoren  ·  {len(role_data["Aktor"])} Aktoren  ·  {sum(not r.dpt for r in self.rows)} ohne ETS-DPT  ·  {sum(unsupported(r.dpt) for r in self.rows)} nicht unterstützt')

    def assign_function(self):
        if not self.project:
            return
        role = self.function.get()
        for iid in self.overview.tree.selection():
            self.project.set_role(self.rows[int(iid)], '' if role == 'Nicht importieren' else role)
        self.refresh()

    def select_type(self, role):
        selected = self.role_tables[role].tree.selection()
        if selected:
            types = {self.rows[int(i)].type_id for i in selected}
            self.type_vars[role].set(TYPE_LABELS.get(next(iter(types)), '') if len(types) == 1 else '')

    def assign_type(self, role):
        type_id = next((k for k, v in TYPE_LABELS.items() if v == self.type_vars[role].get()), None)
        if type_id is None:
            return
        for iid in self.role_tables[role].tree.selection():
            self.project.set_type(self.rows[int(iid)], type_id)
        self.refresh()

    def review(self):
        if not self.project:
            return
        plan = self.project.preview(self.rows, self.target.get())
        if not plan:
            messagebox.showinfo('Keine Auswahl', 'Bitte zuerst Adressen einer Funktion zuordnen.')
            return
        win = tk.Toplevel(self)
        win.title('3 · Importübersicht')
        win.geometry('1280x700')
        win.minsize(1000, 600)
        win.transient(self)
        win.grab_set()
        errors = sum(bool(issue) for _, issue in plan)
        summary = tk.StringVar()
        ttk.Label(win, textvariable=summary, font=('Segoe UI', 17, 'bold'), padding=16).pack(anchor='w')
        ttk.Label(win, text=f'Quelle: {self.project.path.name}\nZiel: {self.target.get()}', padding=(16, 0)).pack(anchor='w')
        table = FilterTable(win, ('Adresse', 'Name', 'ETS-DPT', 'Funktion', 'Loxone-Typ', 'Kategorie', 'Raum', 'Prüfung'), (90, 260, 110, 100, 300, 170, 170, 280))
        table.pack(fill='both', expand=True, padx=16, pady=12)
        foot = ttk.Frame(win, padding=16)
        foot.pack(side='bottom', before=table, fill='x')
        confirmed = tk.BooleanVar(value=False)
        actions = ttk.Frame(foot)
        actions.pack(side='bottom', fill='x', pady=(8, 0))
        ttk.Button(actions, text='← Zurück', command=win.destroy).pack(side='left')
        button = ttk.Button(actions, text='Neue Loxone-Datei erstellen …', state='disabled', command=lambda: self.save(win))
        button.pack(side='right')
        current = ttk.Button(actions, text='Importieren in aktuelle Loxone Datei', style='Accent.TButton', state='disabled', command=lambda: self.save(win, current=True))
        current.pack(side='right', padx=8)

        def enable():
            for b, update_existing in ((button, False), (current, True)):
                valid = not any(issue for _, issue in self.project.preview(self.rows, self.target.get(), update_existing=update_existing))
                b.configure(state='normal' if confirmed.get() and valid else 'disabled')

        def refresh_review():
            confirmed.set(False)
            self.refresh()
            updated = self.project.preview(self.rows, self.target.get(), update_existing=True)
            summary.set(f'{len(updated)} Einträge · {sum(bool(issue) for _, issue in updated)} Konflikte')
            indexes = {id(r): i for i, r in enumerate(self.rows)}
            table.set_data([(indexes[id(r)], (r.ga, r.name, r.dpt or 'Fehlt', r.role, TYPE_LABELS.get(r.type_id, 'Nicht festgelegt'), self.project.categories.get(r.category_id, 'Nicht zugeordnet'), self.project.rooms.get(r.room_id, 'Nicht zugeordnet'), issue or ('Aktuelle Datei: aktualisieren' if self.project.name_matches(r, self.target.get()) else 'Neu anlegen')), ('warning',) if issue else ()) for r, issue in updated])
            enable()

        ttk.Checkbutton(foot, text='Funktionen, Datentypen, Kategorien und Räume geprüft', variable=confirmed, command=enable).pack(anchor='w')
        ttk.Label(foot, text='Aktuelle Datei: gleiche Namen aktualisieren, neue Namen anlegen. Vorher wird eine Sicherungskopie erstellt.').pack(anchor='w')
        self.allocation_controls(win, table, refresh_review)
        refresh_review()

    def save(self, win, current=False):
        if current:
            try:
                count, backup = self.project.export_current(self.rows, self.target.get())
                messagebox.showinfo('Import abgeschlossen', f'{count} KNX-Objekte in die aktuelle Datei importiert.\n\nSicherung: {backup}\n\nDie Datei in Loxone Config neu öffnen, um die Änderungen zu sehen.', parent=win)
                win.destroy()
                self.refresh()
            except Exception as exc:
                messagebox.showerror('Import fehlgeschlagen', str(exc), parent=win)
            return
        dest = filedialog.asksaveasfilename(parent=win, **dialog_location(str(self.project.path)), defaultextension='.Loxone', initialfile=self.project.path.stem + '_KNX_Import.Loxone', filetypes=[('Loxone Config', '*.Loxone')])
        if not dest:
            return
        try:
            count = self.project.export(self.rows, self.target.get(), dest)
            messagebox.showinfo('Datei erstellt', f'{count} neue KNX-Objekte gespeichert:\n{dest}\n\nAnschließend in Loxone Config öffnen und prüfen.', parent=win)
            win.destroy()
        except Exception as exc:
            messagebox.showerror('Export fehlgeschlagen', str(exc), parent=win)


if __name__ == '__main__':
    App().mainloop()
