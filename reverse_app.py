import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from app import FilterTable, dialog_location, position_popup, BG, INK
from reverse_importer import ReverseProject, DPT_CHOICES, address, number
from version import VERSION

BASE = Path(sys.executable if getattr(sys, 'frozen', False) else __file__).resolve().parent
BLUE = '#0879cd'


class ReverseApp(tk.Frame):
    def __init__(self, parent=None):
        self._owns_root = parent is None
        if parent is None:
            parent = tk.Tk()
            parent.title(f'Loxone → ETS · v{VERSION}')
            parent.geometry('1380x800')
            parent.minsize(1100, 650)
        super().__init__(parent, background=BG)
        self.configure(background=BG)
        self.project = None
        self.path = tk.StringVar()
        self.status = tk.StringVar(value='Loxone-Datei auswählen und KNX-Adressen einlesen.')
        style = ttk.Style(self)
        if style.theme_use() != 'clam':
            style.theme_use('clam')
        style.configure('.', font=('Segoe UI', 10), background=BG, foreground=INK)
        style.configure('TButton', padding=(12, 7))
        style.configure('Accent.TButton', background=BLUE, foreground='white', font=('Segoe UI', 10, 'bold'))
        style.map('Accent.TButton', background=[('active', '#0567b0'), ('disabled', '#9dafbf')])
        style.configure('Treeview', rowheight=29, background='white', fieldbackground='white')
        style.map('Treeview', background=[('selected', '#cfe6f7')], foreground=[('selected', '#18354a')])
        style.configure('Treeview.Heading', font=('Segoe UI', 10, 'bold'), padding=(6, 8))
        banner = tk.Frame(self, background='#293944', padx=18, pady=12)
        banner.pack(fill='x')
        logo = Path(sys._MEIPASS) / 'assets' / 'loxone-ets-exporter-logo-bidirectional-v2.png' if getattr(sys, 'frozen', False) else BASE / 'output/logo/loxone-ets-exporter-logo-bidirectional-v2.png'
        raw = tk.PhotoImage(master=self, file=str(logo))
        factor = max(1, (max(raw.width(), raw.height()) + 63) // 64)
        self.logo = raw.subsample(factor, factor)
        self.winfo_toplevel().iconphoto(True, self.logo)
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
        self.table = FilterTable(self, ('Export', 'ETS-Adresse', 'Loxone-Adresse', 'Name', 'ETS-DPT', 'Hauptgruppe', 'Mittelgruppe', 'Prüfung'), (75, 110, 120, 240, 130, 190, 190, 330))
        self.table.pack(fill='both', expand=True, padx=16)
        self.table.tree.bind('<Double-1>', lambda e: self.edit() if self.table.tree.identify_region(e.x, e.y) in ('cell', 'tree') else None)
        files = list(BASE.glob('*.Loxone')) or list(BASE.parent.glob('*.Loxone'))
        files.sort(key=lambda p: ('.backup-' in p.name.casefold(), 'typvorlagen' in p.name.casefold(), p.name.casefold()))
        if files:
            self.path.set(str(files[0]))
        if self._owns_root:
            self.pack(fill='both', expand=True)

    def activate(self):
        style = ttk.Style(self)
        if style.theme_use() != 'clam':
            style.theme_use('clam')
        style.configure('.', font=('Segoe UI', 10), background=BG, foreground=INK)
        style.configure('TButton', padding=(12, 7))
        style.configure('Accent.TButton', background=BLUE, foreground='white', font=('Segoe UI', 10, 'bold'))
        style.map('Accent.TButton', background=[('active', '#0567b0'), ('disabled', '#9dafbf')])
        style.configure('Treeview', rowheight=29, background='white', fieldbackground='white')
        style.map('Treeview', background=[('selected', '#cfe6f7')], foreground=[('selected', '#18354a')])
        style.configure('Treeview.Heading', font=('Segoe UI', 10, 'bold'), padding=(6, 8))

    def withdraw(self):
        self.winfo_toplevel().withdraw()

    def deiconify(self):
        self.winfo_toplevel().deiconify()

    def update(self):
        self.winfo_toplevel().update()

    def geometry(self, value=None):
        return self.winfo_toplevel().geometry(value) if value is not None else self.winfo_toplevel().geometry()

    def wm_frame(self):
        return self.winfo_toplevel().wm_frame()

    def mainloop(self, *args, **kwargs):
        return self.winfo_toplevel().mainloop(*args, **kwargs)

    def destroy(self):
        root = self.winfo_toplevel()
        super().destroy()
        if self._owns_root:
            root.destroy()

    def pick(self):
        chosen = filedialog.askopenfilename(parent=self, **dialog_location(self.path.get()), filetypes=[('Loxone Config', '*.Loxone')])
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
        self.project.ensure_groups()
        self.table.set_data([(i, ('Ja' if r.selected else 'Nein', r.ga, r.original_ga, r.name, 'Ohne DPT' if r.omit_dpt or not r.dpt else r.dpt,
            self.project.main_names.get(int(r.ga.split('/')[0]), ''),
            self.project.middle_names.get(tuple(map(int, r.ga.split('/')[:2])), ''),
            issues.get(id(r)) or r.note or 'Bereit'), ('warning',) if issues.get(id(r)) else ()) for i, r in enumerate(self.project.rows)])
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
            win.transient(self)
            position_popup(win, self, 850, 400)
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
        position_popup(win, self, 700, 450)
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
        win.geometry('760x420')
        win.minsize(700, 400)
        win.transient(self)
        position_popup(win, self, 760, 420)
        win.grab_set()
        box = ttk.Frame(win, padding=18)
        box.pack(fill='both', expand=True)
        ttk.Label(box, text=f'{len(rows)} markierte Einträge neu adressieren', font=('Segoe UI', 14, 'bold')).pack(anchor='w')
        main, middle, _ = rows[0].ga.split('/')
        values = [tk.StringVar(value=main), tk.StringVar(value=middle), tk.StringVar(value='1')]
        group_names = [
            tk.StringVar(value=self.project.main_names.get(int(main), '')),
            tk.StringVar(value=self.project.middle_names.get((int(main), int(middle)), '')),
        ]
        fields = ttk.Frame(box)
        fields.pack(fill='x', pady=12)
        for column, (label, maximum, value) in enumerate(zip(
                ('Hauptgruppe (0–31)', 'Mittelgruppe (0–7)', 'Start-Untergruppe (0–255)'),
                (31, 7, 255), values)):
            ttk.Label(fields, text=label).grid(row=0, column=column, sticky='w', padx=6)
            ttk.Spinbox(fields, from_=0, to=maximum, textvariable=value, width=18).grid(row=1, column=column, sticky='ew', padx=6)
            fields.columnconfigure(column, weight=1)
        name_fields = ttk.Frame(box)
        name_fields.pack(fill='x', pady=(0, 6))
        for column, (label, value) in enumerate(zip(('Name der Hauptgruppe', 'Name der Mittelgruppe'), group_names)):
            ttk.Label(name_fields, text=label).grid(row=0, column=column, sticky='w', padx=6)
            ttk.Entry(name_fields, textvariable=value).grid(row=1, column=column, sticky='ew', padx=6)
            name_fields.columnconfigure(column, weight=1)

        def remember_main_name(*_):
            try:
                main_id = int(values[0].get())
            except ValueError:
                return
            name = group_names[0].get().strip()
            if name:
                self.project.main_names[main_id] = name

        def remember_middle_name(*_):
            try:
                key = (int(values[0].get()), int(values[1].get()))
            except ValueError:
                return
            name = group_names[1].get().strip()
            if name:
                self.project.middle_names[key] = name

        def load_main_name(*_):
            try:
                main_id = int(values[0].get())
            except ValueError:
                return
            group_names[0].set(self.project.main_names.get(main_id, ''))

        def load_middle_name(*_):
            try:
                key = (int(values[0].get()), int(values[1].get()))
            except ValueError:
                return
            group_names[1].set(self.project.middle_names.get(key, ''))

        group_names[0].trace_add('write', remember_main_name)
        group_names[1].trace_add('write', remember_middle_name)
        values[0].trace_add('write', load_main_name)
        values[0].trace_add('write', load_middle_name)
        values[1].trace_add('write', load_middle_name)
        ttk.Label(box, text='Vergabe aufsteigend in Tabellenreihenfolge, nur innerhalb der gewählten Haupt- und Mittelgruppe. Belegte Adressen anderer Einträge werden übersprungen.\nDie Loxone-Datei wird nicht geändert; neue ETS-Adressen sind dort separat abzugleichen.', wraplength=600).pack(anchor='w', pady=12)

        def apply():
            try:
                parts = [value.get().strip() for value in values]
                if any(not part.isascii() or not part.isdigit() for part in parts) or any(int(part) > limit for part, limit in zip(parts, (31, 7, 255))):
                    raise ValueError('Bitte Hauptgruppe 0–31, Mittelgruppe 0–7 und Start-Untergruppe 0–255 eingeben.')
                main_id, middle_id = int(parts[0]), int(parts[1])
                self.project.renumber(rows, '/'.join(parts), within_group=True)
                if group_names[0].get().strip():
                    self.project.main_names[main_id] = group_names[0].get().strip()
                if group_names[1].get().strip():
                    self.project.middle_names[(main_id, middle_id)] = group_names[1].get().strip()
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
        position_popup(win, self, 750, 550)
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
        position_popup(win, self, 1200, 650)
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
        path = filedialog.asksaveasfilename(parent=win, **dialog_location(str(self.project.path)), initialfile=self.project.path.stem + '_ETS_Gruppenadressen.xml', defaultextension='.xml', confirmoverwrite=True, filetypes=[('ETS-Gruppenadressen XML', '*.xml')])
        if path:
            try:
                # The save dialog has already asked the user before returning
                # an existing path. Pass that confirmation through to the
                # atomic replace path instead of trying to create with xb.
                count = self.project.export(path, overwrite=Path(path).exists())
                messagebox.showinfo('Export abgeschlossen', f'{count} Gruppenadressen gespeichert:\n{path}\n\nIn ETS: Gruppenadressen → Rechtsklick → Gruppenadressen importieren.', parent=win)
                win.destroy()
            except Exception as exc:
                messagebox.showerror('Export fehlgeschlagen', str(exc), parent=win)


if __name__ == '__main__':
    root = tk.Tk()
    root.title(f'Loxone → ETS · v{VERSION}')
    root.geometry('1380x800')
    root.minsize(1100, 650)
    app = ReverseApp(root)
    app.pack(fill='both', expand=True)
    root.iconphoto(True, app.logo)
    root.mainloop()
