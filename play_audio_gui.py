#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk
from tkinter.messagebox import showinfo
import warnings
import threading
import argparse
import numpy as np
import sounddevice as sd
import soundfile as sf
import os


# Specify Audio files here, or leave empty to use with command line arg
item_list = [
    'Clapping.wav',
    'applause.wav',
    'applause00.wav',
]
#

parser = argparse.ArgumentParser()
parser.add_argument('-f', '--file', help='input file', action='append')
parser.add_argument('-F', '--files', help='input files', action='append',
                    nargs='*')
parser.add_argument('-d', '--directory',
                    help='input file directory', action='append')
args = parser.parse_args()

if any(vars(args).values()):
    item_list = []  # clearing list if user specified
    if args.file:
        item_list = args.file
    if args.files:
        item_list.extend(*args.files)
    if args.directory:
        for d in args.directory:
            for file_name in os.listdir(d):
                item_list.append(os.path.join(d, file_name))


def load_audio(file_name):
    # load data and fs, or None
    try:
        f = sf.SoundFile(file_name)
        data = f.read(always_2d=True)
        fs = f.samplerate
    except Exception as e:
        print(str(e))
        f = None
        data = None
        fs = None
    return f, data, fs


def sanitize_audio_data(audio_data_list):
    # if not equal, extend length and channels.
    max_len = np.max([a.shape[0] if a is not None else 0 for a in
                      audio_data_list])
    max_ch = np.max([a.shape[1] if a is not None else 0 for a in
                     audio_data_list])
    for idx in range(len(audio_data_list)):
        b = np.zeros((max_len, max_ch))
        if audio_data_list[idx] is not None:
            b[:audio_data_list[idx].shape[0], :audio_data_list[idx].shape[1]] = \
                audio_data_list[idx]
        audio_data_list[idx] = b
    return audio_data_list


class PlayAudioApp(tk.Tk):
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
        self.loop_checkbtn_var = tk.IntVar(self)

        # set up audio items
        self.load_audio_data(item_list)

        # create widget
        self.create_wigets()

        # activate buttons if data present
        self.activate_items()

        # lock for audio data
        self.event = threading.Event()

        # set up audio stream (with default)
        self.current_frame = 0
        self.stream_data = None  # should be protected with self.event
        self.audio_gain = 1.0
        try:
            self.init_audio_stream()
        except Exception as e:
            print(str(e))

        self.protocol("WM_DELETE_WINDOW", self.quit)

    def create_wigets(self):
        # padding for widgets using the grid layout
        paddings = {'padx': 5, 'pady': 5}

        # frames
        device_frame = ttk.Frame(self)
        controls_frame = ttk.Frame(self)
        items_frame = ttk.Frame(self, relief='groove', borderwidth=2)

        # Output device options
        device_label = ttk.Label(device_frame, text='Select output device:')
        device_label.grid(column=0, row=0, sticky=tk.W, **paddings)
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
        button_output_device_info = ttk.Button(device_frame, text="Device Info",
                                               command=
                                               self.output_device_infobox)
        button_output_device_info.grid(column=2, row=0, sticky=tk.W, **paddings)
        self.volume_dB_var = tk.DoubleVar()
        volume_slider = tk.Scale(device_frame, from_=-60, to=+12, length=150,
                                 label='Volume', orient=tk.HORIZONTAL,
                                 command=self.set_volume)
        volume_slider.grid(column=0, row=1, sticky=tk.W, **paddings)

        # start stop controls
        self.start_button = tk.Button(controls_frame, text='Play', bg='green',
                                      command=self.start_audio_stream,
                                      height=2, width=5)
        self.start_button.pack(side=tk.LEFT, **paddings)
        self.stop_button = tk.Button(controls_frame, text='Stop', bg='red',
                                     command=self.stop_audio_stream,
                                     height=2, width=5)
        self.stop_button.pack(side=tk.LEFT, **paddings)
        self.loop_checkbutton = ttk.Checkbutton(controls_frame, text='Loop',
                                                variable=self.loop_checkbtn_var)
        self.loop_checkbutton.pack(side=tk.LEFT, **paddings)

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
                                     command=lambda t=i: self.on_item_button(t),
                                     height=8, width=15, default='disabled',
                                     relief='raised', wraplength='3cm'))
            self.item_buttons[i].grid(column=i, row=2, sticky="nsew",
                                      **paddings)

    def option_changed_device(self, *args):
        self.output_device = self.option_device_var.get()
        try:
            self.init_audio_stream()
        except Exception as e:
            print(str(e))

    def output_device_infobox(self):
        dev_info = sd.query_devices(device=self.output_device)
        showinfo(title='Audio Device Info', message=f'Selected\n {dev_info}')

    def load_audio_data(self, item_list):
        self.fhandles = []
        self.audio_data = []
        self.audio_fs = []
        if item_list:
            for item in item_list:
                file_handle, item_audio, item_fs = load_audio(item)
                self.fhandles.append(file_handle)
                self.audio_data.append(item_audio)
                self.audio_fs.append(item_fs)
        self.item_count = len(self.audio_data)

    def play_audio_callback(self, outdata, frames, time, status):
        self.event.clear()
        if status:
            print(status)
        chunksize = min(len(self.stream_data) - self.current_frame, frames)
        outdata[:chunksize] = self.audio_gain * \
            self.stream_data[self.current_frame:
                             self.current_frame + chunksize]
        if chunksize < frames:
            outdata[chunksize:] = 0
            if self.loop_checkbtn_var.get():
                self.current_frame = 0
            else:
                print('End of file')
                raise sd.CallbackStop
        self.current_frame += chunksize
        self.event.set()

    def init_audio_stream(self):
        if self.item_count == 0:
            raise ValueError("No audio files!")

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
            self.event.set()
            self.switch_audio(0)
            fs = self.audio_fs[0]
            num_ch = self.audio_data[0].shape[1]
            device = self.output_device
            try:
                self.stream = sd.OutputStream(
                    samplerate=fs, device=device, channels=num_ch,
                    callback=self.play_audio_callback,
                    finished_callback=self.event.set)
            except Exception as e:
                print(str(e))

    def activate_items(self):
        for idx, ch in enumerate(self.audio_data):
            if ch is None:
                self.item_buttons[idx].config(state="disabled")
            else:
                self.item_buttons[idx].config(state="active")

    def set_volume(self, volume_dB):
        if isinstance(volume_dB, str):
            volume_dB = int(volume_dB)
        self.audio_gain = 10**(volume_dB / 20)

    def start_audio_stream(self):
        if self.stream is not None:
            self.stream.start()
            self.stop_button['relief'] = 'raised'
            self.start_button['relief'] = 'sunken'

    def stop_audio_stream(self):
        if self.stream is not None:
            if self.stream.stopped:
                self.current_frame = 0
            self.stream.stop()
        self.start_button['relief'] = 'raised'

    def close_audio_stream(self):
        if self.stream is not None:
            self.stream.abort()
            self.stream.close()

    def close_audio_files(self):
        if self.fhandles:
            for f in self.fhandles:
                if f is not None:
                    f.close()

    def switch_audio(self, id):
        self.event.wait()
        self.stream_data = self.audio_data[id]
    
    def on_item_button(self, id):
        self.switch_audio(id)
        for btn in self.item_buttons:
            btn['relief'] = 'raised'
            btn['fg'] = 'black'

        self.item_buttons[id]['relief'] = 'sunken'
        self.item_buttons[id]['fg'] = 'dark green'

    def quit(self):
        print("BYE")
        self.close_audio_stream()
        self.close_audio_files()
        self.destroy()


def main():
    app = PlayAudioApp()
    app.mainloop()


if __name__ == '__main__':
    main()
