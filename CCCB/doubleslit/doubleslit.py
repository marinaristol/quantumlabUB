#to download precomputed simulations go to
# https://drive.google.com/file/d/15Nx16HwFmgWJgWwSQA-WWef3ev0co4ZR/view?usp=sharing

import numpy as np
import threading
import random

from time import time

#cranknicolson imports
from dsexperiment import DSexperiment
from dsexperiment import create_experiment_from_files

from kivy import Config
Config.set('graphics', 'multisamples', '0')
Config.set('graphics', 'fullscreen', 'auto')

#kivy imports
from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.properties import ObjectProperty, NumericProperty
from kivy.graphics import Rectangle, Ellipse
from kivy.graphics.texture import Texture
from kivy.graphics import Color
from kivy.clock import Clock
from kivy.core.audio import SoundLoader
from kivy.uix.image import Image
from kivy.uix.behaviors import ButtonBehavior
from kivy.garden.matplotlib.backend_kivyagg import FigureCanvasKivyAgg

import matplotlib
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
plt.style.use('dark_background')
font = {'family' : 'normal',
        'weight' : 'bold',
        'size'   : 22}

matplotlib.rc('font', **font)


#Initialization of the plots:
fig_qua = Figure()
aqu = fig_qua.add_subplot(111)
aqu.axis('off')


class DoubleSlitScreen(BoxLayout):
    beep= SoundLoader.load('ping.wav')

    #Objects binded from .kv file
    p_rectangle = ObjectProperty()

    button_1slit = ObjectProperty()
    button_2slits = ObjectProperty()

    button_large = ObjectProperty()
    button_medium = ObjectProperty()
    button_small = ObjectProperty()

    button_CA = ObjectProperty()
    button_ES = ObjectProperty()
    button_EN = ObjectProperty()

    label_speed = ObjectProperty()

    speed_slider = ObjectProperty()

    widget_plot = ObjectProperty()


    #Objects created here
    frame = NumericProperty(0) #current frame
    frames = NumericProperty(0) #total number of frames
    texture = ObjectProperty() #texture object (initialized at create_texture)
    zoom = NumericProperty(1) #this value autoadjusts when calling blit_P

    #Drawing parameters
    #size and position of he heatmap
    wh = 0
    hh = 0
    xh = 0
    yh = 0

    #Playback status and settings
    clock = None
    speed = NumericProperty(4)
    playing = True
    normalize_each_frame = True
    loop = True
    lasttime = time()

    #Simulation results
    Pt = None
    times = None
    maxP = 1

    slits = 2
    slit_size = "medium"

    current_filename = "lastsim"

    language = 0
    strings = {
    'slit': ['1 escletxa', '1 ranura', '1 slit'],
    'slits': ['2 escletxes', '2 ranuras', '2 slits'],
    'large': ['Grans', 'Grandes', 'Large'],
    'medium': ['Mitjanes', 'Medianas', 'Medium'],
    'small': ['Petites', 'Pequeñas', 'Small'],
    'speed': ['Velocitat', 'Velocidad', 'Speed']}

    measures_popup = ObjectProperty()

    def __init__(self, *args, **kwargs):
        super(DoubleSlitScreen, self).__init__(*args, **kwargs)

        self.canvas_qua = FigureCanvasKivyAgg(fig_qua)

        self.widget_plot.add_widget(self.canvas_qua)

        #Tries to load old simulation, in case there isn't any, it creates an
        #empty experiment with only psi(t=0)
        print("Trying to load last simulation")
        try:
            self.load_experiment()
        except FileNotFoundError:
            print("Could not find last simulation, creating new one...")
            self.experiment = DSexperiment()
            self.experiment.set_gaussian_psi0(p0x = 150/self.experiment.Lx)
            self.maxP = np.max(self.experiment.Pt)

        self.create_textures()
        self.clock = Clock.schedule_interval(self.update, 1.0 / 30.0)



    def set_language(self, lang):
        self.language = lang
        self.button_1slit.text = self.strings['slit'][self.language]
        self.button_2slits.text = self.strings['slits'][self.language]
        self.button_large.text = self.strings['large'][self.language]
        self.button_medium.text = self.strings['medium'][self.language]
        self.button_small.text = self.strings['small'][self.language]
        self.label_speed.text = self.strings['speed'][self.language]

    def load_experiment(self):
        self.experiment = create_experiment_from_files("{}_{}".format(self.slits, self.slit_size))
        print("Simulation loaded correctly")
        self.computation_done(save = False)
        self.remove_measurements()
        self.experiment.compute_py(force = True)
        aqu.cla()
        aqu.get_xaxis().set_ticks([])
        aqu.get_yaxis().set_ticks([])
        aqu.plot(np.arange(-self.experiment.Ly, self.experiment.Ly, self.experiment.dx), self.experiment.py, c = "g", lw = 4)
        aqu.set_xlim(-self.experiment.Ly, self.experiment.Ly)
        aqu.set_ylim(0,np.max(self.experiment.py))
        self.canvas_qua.draw()



    #Drawing functions
    def create_textures(self):
        """
        Creates the textures that will be used (for the wavefunction and for the potential (slits) )
        """
        self.texture_psi = Texture.create(size = self.experiment.Pt[0].shape[::-1], colorfmt = "luminance", bufferfmt = "float")
        self.texture_V = Texture.create(size = self.experiment.Pt[0].shape[::-1], colorfmt = "rgba", bufferfmt = "float")

    wall_color = (200, 0, 255)

    def blit_P(self, P):
        """
        This function draws the heatmap for P centered at
        P is a 2d numpy array
        """

        #Basically if white should represent the maximum value of P at each frame
        #or should represent the maximum value of all frames
        if self.normalize_each_frame:
            max = np.max(P)
        else:
            max = self.maxP

        #Stores the P matrix in the texture object
        #this texture is created in the method creature_texture and already has the size
        #It's a gray-scale texture so value must go from 0 to 255 (P/self.maxP)*255
        #It must be an array of unsigned 8bit integers. And also it has to be flattened

        self.texture_psi.blit_buffer( ((P[:,::-1]/max)).astype(np.float32).reshape(P.size), colorfmt = "luminance", bufferfmt = "float")

        #Draws walls
        with self.p_rectangle.canvas:
            #Determines the size of the box:
            #Full height
            self.zoom = self.p_rectangle.height/P.shape[0]
            #If full height implies cutting by the sides, it uses full width
            if P.shape[1]*self.zoom > self.p_rectangle.width:
                #Full width
                self.zoom = self.p_rectangle.width/P.shape[1]

            self.wh = P.shape[1]*self.zoom
            self.hh = P.shape[0]*self.zoom

            self.xh = self.p_rectangle.pos[0] + self.p_rectangle.width/2 - self.wh/2
            self.yh = self.p_rectangle.pos[1] + self.p_rectangle.height/2 - self.hh/2

            Color(self.wall_color[0]/255, self.wall_color[1]/255, self.wall_color[2]/255) #Red
            #box wall
            Rectangle(pos = (self.xh-5, self.yh-5), size = (self.wh+10, self.hh+10))

            #Heatmap
            Color(1., 1., 1.) #White
            Rectangle(texture = self.texture_psi, pos = (self.xh, self.yh), size = (self.wh, self.hh))

    def draw_slits(self):
        """
        Draws the slits (heatmap of the potential energy)
        """
        with self.p_rectangle.canvas:
            V = self.experiment.V[:,::-1]
            Vo = self.experiment.Vo

            M = np.zeros((V.shape[0], V.shape[1], 4), dtype = np.float32)
            for i in range(3):
                M[:,:,i] = (self.wall_color[i]*V/Vo).astype(np.float32)
            M[:,:,3] = M[:,:,0]

            self.texture_V.blit_buffer( M.reshape(M.size), colorfmt = "rgba", bufferfmt = "float")

            Rectangle(texture = self.texture_V, pos = (self.xh, self.yh), size = (self.wh, self.hh))


    def draw_measures(self):
        """
        Draws points representing measures in the main UI
        """

        with self.p_rectangle.canvas:
            scale = self.zoom/self.experiment.dx

            #Measuring screen
            Color(0, 1., 0, 0.25)
            Rectangle(pos = (self.xh + self.wh - self.experiment.mp*self.zoom, self.yh), size = (self.experiment.mw*self.zoom, self.hh))

            Color(0, 1., 0)
            for measure in self.experiment.measurements:
                Ellipse(pos = (self.xh + self.wh - 2*self.experiment.mp*self.zoom + measure[0]*self.zoom , self.yh + measure[1]*self.zoom), size = (self.zoom, self.zoom))

    def computation_update(self, msg, x):
        """
        This is called by the thread computing the simulation
        """
        pass

    def computation_done(self, save = True):
        """
        This is called when the simulation has been completed
        """
        self.frames = self.experiment.Pt.shape[0]
        self.maxP = np.max(self.experiment.Pt)
        self.create_textures()


        if save:
            self.experiment.save_to_files("lastsim")

    def slider_moved(self, a, b):
        Clock.schedule_once(self.reset_speed, 5*60)

    def reset_speed(self, a):
        self.speed_slider.value = 5

    #Playback functions
    def playpause(self):
        self.playing = not self.playing
        if self.playing:
            self.clock = Clock.schedule_interval(self.update, 1.0 / 30.0)
            self.playpause_button.text = "Pause experiment"
        else:
            self.clock.cancel()
            self.playpause_button.text = "Start experiment"

    def change_frame(self):
        self.playing = False

    bins = 40
    Nexp = 200
    def measure(self, N = 1):
        self.experiment.measure(N)
        dx = 2*self.experiment.Ly/self.bins
        A = max(self.Nexp,len(self.experiment.measurements))*dx
        #self.beep.play()
        aqu.cla()
        aqu.get_xaxis().set_ticks([])
        aqu.get_yaxis().set_ticks([])
        aqu.hist([-self.experiment.Ly + measure[1]*self.experiment.dx for measure in self.experiment.measurements], range = (-self.experiment.Ly,self.experiment.Ly), bins = self.bins, edgecolor='g')
        aqu.set_xlim(-self.experiment.Ly, self.experiment.Ly)
        aqu.set_ylim(0,np.max(self.experiment.py*A))
        aqu.plot(np.arange(-self.experiment.Ly, self.experiment.Ly, self.experiment.dx), self.experiment.py*A, c="g", lw = 4)
        self.canvas_qua.draw()


    def remove_measurements(self):
        self.experiment.clear_measurements()


    lang_dict = {'CA': 0, 'ES': 1, 'EN': 2}

    def button_toggled(self, button):
        if button.name in ["1", "2"]:
            self.button_1slit.color = (1.0, 1.0, 1.0, 1.0)
            self.button_2slits.color = (1.0, 1.0, 1.0, 1.0)
            self.last_number = button
            button.color = (0,0.75,1,1)
            self.slits = int(button.name)
            self.load_experiment()
        elif button.name in ["small", "medium", "large"]:
            self.button_small.color = (1.0, 1.0, 1.0, 1.0)
            self.button_medium.color = (1.0, 1.0, 1.0, 1.0)
            self.button_large.color = (1.0, 1.0, 1.0, 1.0)
            self.last_size = button
            button.color = (0,0.75,1,1)
            self.slit_size = button.name
            self.load_experiment()
        elif button.name in ["CA", "ES", "EN"]:
            self.button_CA.color = (1.0, 1.0, 1.0, 1.0)
            self.button_ES.color = (1.0, 1.0, 1.0, 1.0)
            self.button_EN.color = (1.0, 1.0, 1.0, 1.0)
            self.last_lang = button
            button.color = (0,0.75,1,1)
            self.set_language(self.lang_dict[button.name])


        print(self.slits, self.slit_size)

    def update(self, dt):

        self.speed = int(self.speed_slider.value)

        if self.playing:
            self.p_rectangle.canvas.clear()
            self.blit_P(self.experiment.Pt[self.frame])
            self.draw_slits()
            self.draw_measures()
            self.frame = (self.frame+self.speed)

            if self.frame >= self.frames:
                if self.beep:
                    self.beep.play()
                self.measure()
                if self.loop:
                    self.frame = self.frame%self.frames
                else:
                    self.frame = 0

        else:
            self.p_rectangle.canvas.clear()
            self.blit_P(self.experiment.Pt[self.frame])
            self.draw_slits()
            self.draw_measures()



class DoubleSlitApp(App):
    def build(self):
        random.seed()
        screen = DoubleSlitScreen()
        return screen

if __name__ == "__main__":
    DoubleSlitApp().run()
