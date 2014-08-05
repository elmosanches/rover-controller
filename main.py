import time
import datetime
import json

from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.properties import NumericProperty, ObjectProperty
from kivy.network.urlrequest import UrlRequest
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.stacklayout import StackLayout
from kivy.graphics import Color, Rectangle
from kivy.clock import Clock
from kivy.logger import Logger

from kivy.support import install_twisted_reactor
install_twisted_reactor()

from twisted.internet import reactor

from twisted.protocols.basic import LineReceiver
from twisted.internet.protocol import ClientFactory


DRIVING_WHEEL_MAX = 100
ACCELLERATOR_MAX = 100

SERVER_HOST = 'localhost'
SERVER_PORT = 8123
CONTROLLER_NAME = 'kivy_ctrl01'


class EndpointClient(LineReceiver):
    def connectionMade(self):
        print "connection made"
        self.factory.connect_protocol(self)

    def lineReceived(self, line):
        self.factory.line_received(line)



class EndpointFactory(ClientFactory):
    protocol = EndpointClient
    connector = None

    def __init__(self, endpoint_communication_bl):
        self.ec_bl = endpoint_communication_bl

    def clientConnectionLost(self, conn, reason):
        print "connection lost"
        self.ec_bl.on_connection_lost(reason)
        self.connector = conn
        Clock.schedule_once(self.try_reconnect_callback, 1)

    def clientConnectionFailed(self, conn, reason):
        print "connection failed"
        self.ec_bl.on_connection_failed(reason)
        self.connector = conn
        Clock.schedule_once(self.try_reconnect_callback, 1)

    def connect_protocol(self, protocol):
        self.ec_bl.on_connection(protocol)

    def line_received(self, line):
        self.ec_bl.protocol_line_received(line)

    def try_reconnect_callback(self, dt):
        self.connector.connect()


class EndpointRequest(object):

    TIME_FORMAT = '%Y%m%d%H%M%S%f'
    TIMEOUT = 15

    def __init__(self, command, value):
        self.command = command
        self.value = value
        self.time = datetime.datetime.utcnow().strftime(self.TIME_FORMAT)

    @classmethod
    def expire_requests(clk, requests_list):
        new_requests = {}
        threshold = (datetime.datetime.utcnow() -\
            datetime.timedelta(seconds=clk.TIMEOUT)).strftime(clk.TIME_FORMAT)
        for rq_id, request in requests_list.items():
            if request.time < threshold:
                Logger.warning("REQUEST TIMEOUT: ID {} COMMAND {} VALUE {}".\
                        format(rq_id, request.command, request.value))
            else:
                new_requests[rq_id] = request

        return new_requests


#@TODO
"""
-healthcheck request
-battery status
"""
class EndpointCommunicationBL(BoxLayout):

    con_widget = ObjectProperty(None)
    bat_widget = ObjectProperty(None)
    utility_lt = ObjectProperty(None)

    available_endpoints = []
    enpoint_is_connected = False
    selected_device = None

    rq_id = 1
    requests_list = {}

    def __init__(self, *args, **kwargs):
        super(EndpointCommunicationBL, self).__init__(*args, **kwargs)

    def connect(self):
        reactor.connectTCP(SERVER_HOST, SERVER_PORT, EndpointFactory(self))

    def on_connection(self, protocol):
        self.protocol = protocol
        self.protocol.sendLine('CC:' + CONTROLLER_NAME)

        self.con_widget.update_status('YELLOW', 'server connected')

    def on_connection_lost(self, reason):
        self.con_widget.update_status('RED', 'no connection')
        self.utility_lt.log_display(reason.getErrorMessage())
        Clock.unschedule(self.send_healthcheck)

    def on_connection_failed(self, reason):
        self.con_widget.update_status('RED', 'no connection')
        self.utility_lt.log_display(reason.getErrorMessage())
        Clock.unschedule(self.send_healthcheck)

    def protocol_line_received(self, line):
        print "line received: {}".format(line)

        header = line[:2]
        body = line[3:]

        if header == 'DL':
            #@TODO
            #handle available devices list
            if self.enpoint_is_connected:
                self.save_available_endpoints(body)
            else:
                self.enpoint_connecting_process(body)

        elif header == 'CD':
            if body == 'OK':
                self.enpoint_is_connected = True
                self.utility_lt.reset()
                self.con_widget.update_status('GREEN', self.selected_device)
            else:
                self.con_widget.update_status('RED', body)

        elif header == 'DD':
            #@TODO
            #handle device disconected
            pass
        elif header == 'RE':
            self.endpoint_request_received(body)
        elif header == 'SE':
            #@TODO
            #handle error
            Logger.warning("SERVER ERROR: {}".format(body))
            pass
        else:
            #@TODO
            #handle undefined command
            Logger.warning("UNDEFINED COMMAND: {}".format(body))
            pass

    def save_available_endpoints(self, body):
        if body:
            self.available_endpoints = body.split(':')
        else:
            self.available_endpoints = []

    def enpoint_connecting_process(self, body):

        self.save_available_endpoints(body)
        self.utility_lt.connecting_endpoint(
            self.available_endpoints, self.on_select_device
        )

    def on_select_device(self, device):
        self.protocol.sendLine('CD:' + device)
        self.selected_device = device

        Clock.schedule_interval(self.send_healthcheck, 0.5)

    def send_healthcheck(self, dt):
        self.send_request(command=0, value=0)

        self.requests_list = EndpointRequest.expire_requests(self.requests_list)

    def endpoint_request_received(self, request_body):
        rq_id, status, result = request_body.split(':')
        rq_id = int(rq_id)
        if status > 0:
            if rq_id > 0:
                self.process_success_response(rq_id, result)
            else:
                self.process_success_unbound_response(result)
        else:
            if rq_id > 0:
                self.process_error_response(rq_id, result)
            else:
                self.process_error_unbound_response(result)

    def process_success_response(self, rq_id, result):
        request = self.requests_list.pop(rq_id, None)
        if request is None:
            Logger.warning("UNEXPECTED REQUEST: id: {}, result: {}".\
                           format(rq_id, result))
            return
        if request.command == 0:
            #update battery status
            self.bat_widget.update_status('GREEN', result.split(',')[0] + ' V')
            #update roundtrip status

            pass

    def process_success_unbound_response(self, result):
        Logger.warning("UNBOUND SUCCESS REQUEST: result: {}".format(result))
    def process_error_response(self, rq_id, result):
        Logger.warning("ERROR REQUEST: id: {}, result: {}".format(rq_id, result))
    def process_error_unbound_response(self, result):
        Logger.warning("UNBOUND ERROR REQUEST: result: {}".format(result))

    def command_wheel(self, value):
        print "command wheel value: {}".format(value)

        value += 100
        value *= 1024/200

        self.send_request(command=1, value=value)

    def command_accell(self, value):
        print "command accell value: {}".format(value)

        value += 100
        value /= 2

        self.send_request(command=2, value=value)

    def get_rq_id(self):
        self.rq_id += 1
        return self.rq_id

    def send_request(self, command, value):
        rq_id = self.get_rq_id()

        self.requests_list[rq_id] = EndpointRequest(command, value)

        body = 'RE:{}:{}:{}'.format(command, int(value), rq_id)
        self.protocol.sendLine(body)


class StatusBL(BoxLayout):

    def update_status(self, color, status_msg):
        with self.canvas.before:
            if color.upper() == 'RED':
                Color(0.5, 0, 0, mode='rgba')
            if color.upper() == 'GREEN':
                Color(0, 0.5, 0, mode='rgba')
            if color.upper() == 'YELLOW':
                Color(0.9, 0.7, 0, mode='rgba')
            Rectangle(
                pos=[self.x, self.y],
                size=[self.width, self.height]
            )

        self.label.text = status_msg


class CommandSenderBL(BoxLayout):

    def update_status(self, color, status_msg):
        with self.canvas.before:
            if color.upper() == 'RED':
                Color(0.5, 0, 0, mode='rgba')
            if color.upper() == 'GREEN':
                Color(0, 0.5, 0, mode='rgba')
            if color.upper() == 'YELLOW':
                Color(0.9, 0.7, 0, mode='rgba')
            Rectangle(
                pos=[self.x, self.y],
                size=[self.width, self.height]
            )

        self.label.text = status_msg


class UtilityLt(StackLayout):
    def reset(self):
        self.clear_widgets()
        self.padding = [0, 0, 0, 0]
        self.spacing = [0, 0]

    def connecting_endpoint(self, available_endpoints, on_select_callback):
        self.on_select_callback = on_select_callback
        self.reset()

        if not available_endpoints:
            lbl = Label(text='no device available', size_hint=(1, 0.15))
            self.add_widget(lbl)
        else:
            self.padding = [50, 5, 50, 5]
            self.spacing = [0, 20]
            lbl = Label(text='select device:', size_hint=(1, 0.15))
            self.add_widget(lbl)
            for device in available_endpoints:
                btn = Button(text=device, size_hint=(1, 0.15))
                btn.bind(on_press=self.on_press_select_device)
                self.add_widget(btn)

    def log_display(self, msg):
        self.reset()
        lbl = Label(text=msg, size_hint=(1, 1))
        self.add_widget(lbl)

    def on_press_select_device(self, instance):
        self.on_select_callback(instance.text)


class Throttle(Widget):
    pass


class Controller(Widget):
    throttle = ObjectProperty(None)
    main_board = ObjectProperty(None)
    value = NumericProperty('0')

    def on_touch_down(self, touch):
        if self.collide_point(touch.x, touch.y):

            touch.grab(self)
            self.throttle.y = touch.y - self.throttle.width / 2
            self._update_value()

        return super(Controller, self).on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.grab_current is self and self.collide_point(self.x, touch.y):

            self.throttle.y = touch.y - self.throttle.width / 2
            self._update_value()

        return super(Controller, self).on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:

            touch.ungrab(self)
            self.throttle.y = self.center_y - self.throttle.width / 2
            self._update_value()

        return super(Controller, self).on_touch_up(touch)

    def _update_value(self):
        t_value = self.throttle.y + self.throttle.width / 2 - self.center_y
        self.value = int(round(self.MAX_VALUE / (self.height / 2) * t_value))


class Wheel_Controller(Controller):

    MAX_VALUE = DRIVING_WHEEL_MAX

    def _update_value(self):
        super(Wheel_Controller, self)._update_value()

        self.main_board.update_wheel(self.value)


class Accell_Controller(Controller):

    MAX_VALUE = ACCELLERATOR_MAX

    def _update_value(self):
        super(Accell_Controller, self)._update_value()

        self.main_board.update_accell(self.value)


class MainBoard(Widget):
    driving_wheel = ObjectProperty(None)
    accelleration = ObjectProperty(None)
    endpoint_conn = ObjectProperty(None)

    def connect_to_server(self):
        self.endpoint_conn.connect()

    def update_wheel(self, value):
        self.endpoint_conn.command_wheel(value)

    def update_accell(self, value):
        self.endpoint_conn.command_accell(value)


class RoverApp(App):
    def build(self):
        main_board = MainBoard()
        main_board.connect_to_server()

        return main_board


if __name__ == '__main__':
    RoverApp().run()
