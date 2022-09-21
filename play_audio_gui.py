#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk
from tkinter.messagebox import showinfo
import numpy as np
import sounddevice as sd
import soundfile as sf
import warnings
import threading


### Specify Audio files here:
item_list = [
    'Clapping.wav',
    'applause.wav',
    'applause00.wav',
]
###



current_frame = 0
data = 0
event = threading.Event()

def load_audio(file_name):
    try:
        data, fs = sf.read(file_name, always_2d=True)
    except Exception as e:
        print(str(e))
        data = None
        fs = None
    return data, fs

def play_audio_callback(outdata, frames, time, status):
    global current_frame
    if status:
        print(status)
    chunksize = min(len(data) - current_frame, frames)
    outdata[:chunksize] = data[current_frame:current_frame + chunksize]
    if chunksize < frames:
        outdata[chunksize:] = 0
        raise sd.CallbackStop()
    current_frame += chunksize

def sanitize_audio_data(audio_data_list):
    # if not equal, extend length and channels.
    max_len = np.max([a.shape[0] if a is not None else 0 for a in
                      audio_data_list])
    max_ch = np.max([a.shape[1] if a is not None else 0 for a in
                     audio_data_list])
    for idx in range(len(audio_data_list)):
        b = np.zeros((max_len, max_ch))
        if audio_data_list[idx] is not None:
            b[:audio_data_list[idx].shape[0],:audio_data_list[idx].shape[1]] = \
                audio_data_list[idx]
        audio_data_list[idx] = b
    return audio_data_list



class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.geometry("640x320")
        self.title('Play Audio')
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # initialize data
        self.stream = None
        self.devices = (["--- Not probed yet ---"])
        self.output_device = None
        self.option_device_var = tk.StringVar(self)

        # set up audio items
        self.item_count = len(item_list)
        self.load_audio_data(item_list)

        # create widget
        self.create_wigets()

        # activate buttons if data present
        self.activate_items()

        # set up audio stream (with default)
        self.init_audio_stream()

    def create_wigets(self):
        # padding for widgets using the grid layout
        paddings = {'padx': 5, 'pady': 5}

        # frames
        device_frame = ttk.Frame(self)
        controls_frame = ttk.Frame(self)
        items_frame = ttk.Frame(self, relief='groove', borderwidth=2)

        # Output device options
        label = ttk.Label(device_frame,  text='Select output device:')
        label.grid(column=0, row=0, sticky=tk.W, **paddings)
        queried_devices = sd.query_devices()
        self.devices = [d.get('name') for d in queried_devices]
        device_option_menu = ttk.Combobox(
            device_frame,
            textvariable=self.option_device_var,
            values=self.devices,
            width=30)
        device_option_menu.bind('<<ComboboxSelected>>',
                                self.option_changed_device)
        device_option_menu.grid(column=1, row=0, sticky=tk.W, **paddings)
        button_output_device_info = ttk.Button(device_frame,text="Device Info",
            command=self.output_device_infobox)
        button_output_device_info.grid(column=2, row=0, sticky=tk.W, **paddings)

        # start stop controls
        self.start_button = tk.Button(controls_frame, text='Play', bg='green',
                                      command=self.start_audio_stream)
        self.start_button.pack(side=tk.LEFT)
        self.stop_button = tk.Button(controls_frame, text='Stop', bg='red',
                                      command=self.stop_audio_stream)
        self.stop_button.pack(side=tk.LEFT)

        # items
        self.create_item_buttons(items_frame, self.item_count, paddings)

        # position frames
        device_frame.grid(row=0, rowspan=2, columnspan=3, sticky='EW',
                          **paddings)
        controls_frame.grid(row=1, rowspan=2, columnspan=3, sticky='N',
                            **paddings)
        items_frame.grid(row=3, rowspan=2, columnspan=3, sticky='EW', 
                         **paddings)


    def create_item_buttons(self, container, amount, paddings):
        self.item_buttons = []
        for i in range(amount):
            self.item_buttons.append(tk.Button(container, text=item_list[i],
                                     command=lambda t=i: self.switch_audio(t),
                                     height=8, width=15, default='disabled'))
            self.item_buttons[i].grid(column=i, row=2, sticky="nsew",
                                      **paddings)

    def option_changed_device(self, *args):
        self.output_device = self.option_device_var.get()
        self.init_audio_stream()
    
    def output_device_infobox(self):
        dev_info = sd.query_devices(device=self.output_device)
        showinfo(title='Audio Device Info', message=f'Selected\n {dev_info}')

    def load_audio_data(self, item_list):
        self.audio_data = []
        self.audio_fs = []
        for item in item_list:
            item_audio, item_fs = load_audio(item)
            self.audio_data.append(item_audio)
            self.audio_fs.append(item_fs)

    def init_audio_stream(self):
        self.audio_data = sanitize_audio_data(self.audio_data)
        if self.stream is not None:
            if any(elem is None for elem in self.audio_fs):
                warnings.warn("Empty item")
            else:
                if not all(self.audio_fs[0] == itfs for itfs in self.audio_fs):
                    warnings.warn("Samplerate not consistent")
                if not all(self.audio_data[0].shape[1] == itch.shape[1] 
                    for itch in self.audio_data):
                    warnings.warn("Channel count not consistent")

        # init audio
        if len(self.audio_data[0]) == 0:
            warnings.warn("Empty first item, not able to initialize audio.")
        else:
            global data
            data = self.audio_data[0]
            fs = self.audio_fs[0]
            num_ch = self.audio_data[0].shape[1]
            device = self.output_device
            try:
                self.stream = sd.OutputStream(
                    samplerate=fs, device=device, channels=num_ch,
                    callback=play_audio_callback, finished_callback=event.set)
            except Exception as e:
                print(str(e))

    def activate_items(self):
        for idx, ch in enumerate(self.audio_data):
            if ch is None:
                self.item_buttons[idx].config(state="disabled")
            else:
                self.item_buttons[idx].config(state="active")


    def start_audio_stream(self):
        if self.stream is not None:
            self.stream.start()
            self.stop_button['relief'] = 'raised'
            self.start_button['relief'] = 'sunken'

    def stop_audio_stream(self):
        if self.stream is not None:
            if self.stream.stopped:
                global current_frame
                current_frame = 0
            self.stream.stop()
        self.start_button['relief'] = 'raised'

    def close_audio_stream(self):
        if self.stream is not None:
            self.stream.close()

    def switch_audio(self, id):
        global data
        data = self.audio_data[id]

    def quit(self):
        print("BYE")
        self.close_audio_stream()
        self.destroy()




if __name__ == "__main__":
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.quit)
    app.mainloop()

