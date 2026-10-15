import tkinter as tk
from tkinter import ttk

from app import App, BG, INK
from reverse_app import ReverseApp
from version import VERSION


class CombinedApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f'ETS ↔ Loxone · v{VERSION}')
        self.geometry('1380x860')
        self.minsize(1100, 720)
        self.configure(background=BG)

        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('Switcher.TNotebook', background=BG, borderwidth=0)
        style.configure('Switcher.TNotebook.Tab', padding=(22, 10), background='#e1e4e6', foreground=INK)
        style.map('Switcher.TNotebook.Tab', background=[('selected', 'white')], foreground=[('selected', '#4c8c20')])

        self.switcher = ttk.Notebook(self, style='Switcher.TNotebook')
        self.switcher.pack(fill='both', expand=True)

        importer_tab = tk.Frame(self.switcher, background=BG)
        exporter_tab = tk.Frame(self.switcher, background=BG)
        self.importer = App(importer_tab)
        self.importer.pack(fill='both', expand=True)
        self.exporter = ReverseApp(exporter_tab)
        self.exporter.pack(fill='both', expand=True)

        self.switcher.add(importer_tab, text='ETS → Loxone')
        self.switcher.add(exporter_tab, text='Loxone → ETS')
        self.iconphoto(True, self.importer.logo)
        self.switcher.bind('<<NotebookTabChanged>>', self._activate_selected)
        self.switcher.select(importer_tab)
        self.importer.activate()

    def _activate_selected(self, _event=None):
        selected = self.switcher.select()
        if selected == str(self.importer.master):
            self.importer.activate()
        elif selected == str(self.exporter.master):
            self.exporter.activate()


if __name__ == '__main__':
    CombinedApp().mainloop()
