"""Opt-in system volume settings for the two selected devices."""

import tkinter as tk

from .. import config, i18n
from . import widgets

C = config.COLORS


class VolumeLockDialog:
    def __init__(self, parent, fonts, lang, options, device_names, on_apply, extra_devices=()):
        self._tr = lambda key: i18n.tr(lang, key)
        self._on_apply = on_apply
        self._options = dict(options)
        self.window = win = tk.Toplevel(parent)
        win.withdraw()
        win.title(self._tr('volume_lock_title'))
        win.configure(bg=C['panel'])
        win.resizable(False, False)
        win.transient(parent)
        win.protocol('WM_DELETE_WINDOW', self.close)
        self.enabled = tk.BooleanVar(win, options['enabled'])
        self.input_enabled = tk.BooleanVar(win, options['input_enabled'])
        self.output_enabled = tk.BooleanVar(win, options['output_enabled'])
        self.input_level = tk.StringVar(win, str(options['input_level']))
        self.output_level = tk.StringVar(win, str(options['output_level']))
        self.interval = tk.StringVar(win, str(options['interval_seconds']))
        self.extra_inputs = []
        content = tk.Frame(win, bg=C['panel'])
        content.pack(fill='both', expand=True, padx=22, pady=18)
        self._check(content, 'volume_lock_enable', self.enabled, fonts['strong']).pack(anchor='w')
        tk.Label(content, text=self._tr('volume_lock_hint'), bg=C['panel'],
                 fg=C['muted'], font=fonts['muted'], wraplength=540,
                 justify='left').pack(fill='x', pady=(8, 16))
        self.input_spin = self._device_row(content, 'src_mic', device_names[0],
                                          self.input_enabled, self.input_level, fonts)
        self.output_spin = self._device_row(content, 'virt_mic', device_names[1],
                                           self.output_enabled, self.output_level, fonts)
        self._extra_rows(content, extra_devices, options, fonts)
        interval_row = tk.Frame(content, bg=C['panel'])
        interval_row.pack(fill='x', pady=(6, 14))
        tk.Label(interval_row, text=self._tr('volume_lock_interval'), bg=C['panel'],
                 fg=C['text'], font=fonts['body']).pack(side='left')
        self.interval_spin = self._spin(interval_row, self.interval, 1, 300, fonts)
        self.interval_spin.pack(side='left', padx=8)
        tk.Label(interval_row, text=self._tr('volume_lock_seconds'), bg=C['panel'],
                 fg=C['muted'], font=fonts['body']).pack(side='left')
        self.status = tk.Label(content, bg=C['panel'], fg=C['muted'],
                               font=fonts['muted'], wraplength=540, justify='left', anchor='w')
        self.status.pack(fill='x', pady=(0, 8))
        self.error = tk.Label(content, bg=C['panel'], fg=C['danger'],
                              font=fonts['small'], wraplength=540, justify='left', anchor='w')
        self.error.pack(fill='x', pady=(0, 10))
        buttons = tk.Frame(content, bg=C['panel'])
        buttons.pack(fill='x')
        widgets.make_button(buttons, self._tr('volume_lock_apply'), self.apply,
                            font=fonts['strong'], bg=C['green_dark'],
                            hover_bg=C['green']).pack(side='left')
        widgets.make_button(buttons, self._tr('volume_lock_close'), self.close,
                            font=fonts['body']).pack(side='right')
        win.update_idletasks()
        width = 590
        height = win.winfo_reqheight()
        x = parent.winfo_rootx() + max(0, (parent.winfo_width() - width) // 2)
        y = parent.winfo_rooty() + max(0, (parent.winfo_height() - height) // 2)
        win.geometry('%dx%d+%d+%d' % (width, height, x, y))
        win.deiconify()
        win.grab_set()
        win.focus_set()

    def _check(self, parent, key, variable, font):
        return tk.Checkbutton(parent, text=self._tr(key), variable=variable,
                              bg=C['panel'], fg=C['text'], selectcolor=C['panel_lighter'],
                              activebackground=C['panel'], activeforeground=C['text'],
                              font=font, highlightthickness=0, anchor='w', padx=0)

    def _spin(self, parent, variable, low, high, fonts):
        return tk.Spinbox(parent, textvariable=variable, from_=low, to=high, width=5,
                          font=fonts['body'], bg=C['panel_soft'], fg=C['text'],
                          insertbackground=C['text'], buttonbackground=C['panel_lighter'],
                          relief='flat', justify='center', highlightthickness=1,
                          highlightbackground=C['border'], highlightcolor=C['blue'])

    def _device_row(self, parent, key, name, enabled, value, fonts):
        row = tk.Frame(parent, bg=C['panel'])
        row.pack(fill='x', pady=(0, 14))
        heading = tk.Frame(row, bg=C['panel'])
        heading.pack(fill='x')
        self._check(heading, key, enabled, fonts['strong']).pack(side='left')
        tk.Label(heading, text='%', bg=C['panel'], fg=C['muted'],
                 font=fonts['body']).pack(side='right')
        spin = self._spin(heading, value, 0, 100, fonts)
        spin.pack(side='right', padx=(0, 6))
        tk.Label(row, text=name, bg=C['panel'], fg=C['muted'],
                 font=fonts['muted'], wraplength=530, justify='left',
                 anchor='w').pack(fill='x', padx=(22, 0), pady=(3, 0))
        return spin

    def _extra_rows(self, parent, discovered, options, fonts):
        saved = {item['endpoint_id']: dict(item) for item in options.get('extra_inputs', [])}
        devices = []
        for item in discovered:
            endpoint = item['endpoint_id']
            previous = saved.pop(endpoint, None)
            devices.append(dict(item, enabled=previous['enabled'] if previous else True,
                                level=previous['level'] if previous else options['output_level']))
        devices.extend(dict(item, missing=True) for item in saved.values())
        if not devices:
            return
        tk.Label(parent, text=self._tr('volume_lock_extra_title'), bg=C['panel'],
                 fg=C['text'], font=fonts['strong'], anchor='w').pack(fill='x', pady=(0, 3))
        tk.Label(parent, text=self._tr('volume_lock_extra_hint'), bg=C['panel'],
                 fg=C['muted'], font=fonts['muted'], anchor='w',
                 wraplength=540, justify='left').pack(fill='x', pady=(0, 6))
        frame = tk.Frame(parent, bg=C['panel'])
        frame.pack(fill='x', pady=(0, 12))
        canvas = tk.Canvas(frame, bg=C['panel'], height=min(3, len(devices)) * 36,
                            highlightthickness=0, bd=0)
        scroll = tk.Scrollbar(frame, orient='vertical', command=canvas.yview,
                              bg=C['panel_lighter'], troughcolor=C['panel'],
                              activebackground=C['border_strong'], width=12,
                              highlightthickness=0, bd=0)
        scroll.pack(side='right', fill='y')
        canvas.pack(side='left', fill='x', expand=True)
        canvas.configure(yscrollcommand=scroll.set)
        rows = tk.Frame(canvas, bg=C['panel'])
        window = canvas.create_window(0, 0, window=rows, anchor='nw')
        rows.bind('<Configure>', lambda _e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(window, width=e.width))
        for item in devices:
            row = tk.Frame(rows, bg=C['panel'])
            row.pack(fill='x', pady=3)
            enabled = tk.BooleanVar(self.window, item['enabled'])
            level = tk.StringVar(self.window, str(item['level']))
            tk.Label(row, text='%', bg=C['panel'], fg=C['muted'],
                     font=fonts['body']).pack(side='right')
            self._spin(row, level, 0, 100, fonts).pack(side='right', padx=(5, 6))
            label = item['name']
            if item.get('missing'):
                label += ' (' + self._tr('volume_lock_unavailable') + ')'
            check = self._check(row, 'src_mic', enabled, fonts['muted'])
            check.config(text=label, wraplength=400, justify='left')
            check.pack(side='left', fill='x', expand=True)
            self.extra_inputs.append({'endpoint_id': item['endpoint_id'], 'name': item['name'],
                                      'enabled': enabled, 'level': level})

    def apply(self):
        enabled = self.enabled.get()
        try:
            values = [int(v.get()) for v in (self.input_level, self.output_level, self.interval)]
            if not (0 <= values[0] <= 100 and 0 <= values[1] <= 100 and 1 <= values[2] <= 300):
                raise ValueError()
        except ValueError:
            if enabled:
                self.error.config(text=self._tr('volume_lock_invalid'))
                self._fit_height()
                return
            values = [self._options[k] for k in ('input_level', 'output_level', 'interval_seconds')]
        extras = []
        for item in self.extra_inputs:
            try:
                level = int(item['level'].get())
                if not 0 <= level <= 100:
                    raise ValueError()
            except ValueError:
                if enabled and item['enabled'].get():
                    self.error.config(text=self._tr('volume_lock_invalid'))
                    self._fit_height()
                    return
                level = next((old['level'] for old in self._options.get('extra_inputs', [])
                              if old['endpoint_id'] == item['endpoint_id']), 100)
            extras.append({'endpoint_id': item['endpoint_id'], 'name': item['name'],
                           'enabled': item['enabled'].get(), 'level': level})
        if enabled and not (self.input_enabled.get() or self.output_enabled.get()
                            or any(item['enabled'] for item in extras)):
            self.error.config(text=self._tr('volume_lock_select'))
            self._fit_height()
            return
        options = dict(enabled=enabled, input_enabled=self.input_enabled.get(),
                       output_enabled=self.output_enabled.get(), input_level=values[0],
                       output_level=values[1], interval_seconds=values[2], extra_inputs=extras)
        try:
            self._on_apply(options)
        except Exception as exc:
            self.error.config(text=str(exc))
            self._fit_height()
            return
        self._options = options
        self.error.config(text='')
        self._fit_height()

    def set_status(self, status, interval):
        state = status.get('state', 'off')
        text = self._tr('volume_lock_' + state)
        if state == 'on':
            text = text.format(seconds=interval)
        elif state == 'error':
            text += ': ' + status.get('message', '')
        self.status.config(text=text, fg=C['danger'] if state == 'error' else C['muted'])
        self._fit_height()

    def _fit_height(self):
        self.window.update_idletasks()
        self.window.geometry('590x%d' % self.window.winfo_reqheight())

    def close(self):
        self.window.destroy()
