import time
import json

from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.properties import NumericProperty, ObjectProperty
from kivy.network.urlrequest import UrlRequest
from kivy.uix.boxlayout import BoxLayout
from kivy.graphics import Color, Rectangle


DRIVING_WHEEL_MAX = 100
ACCELLERATOR_MAX = 100


class StatusBL(BoxLayout):
    pass


class CommandSenderBL(BoxLayout):

    endpoint = 'http://192.168.0.205:9999'

    connection_status = False

    #@TODO
    def establish_connection(self):
        #discover server
        #retrieve configuration
        #configure connection
        pass

    def get_jrpc_request(self, method, params):
        """
        {"jsonrpc": "2.0", "method": "subtract", "params": [42, 23], "id": 1}
        """
        request = {
            'jsonrpc': '2.0',
            'method': method,
            'params': params,
            'id': 1
        }

        return json.dumps(request)

    def send_rpc_request(self, body):

        headers = {
            'Content-Type': 'application/json',
        }

        req = UrlRequest(
            url=self.endpoint,
            on_success=self._on_success,
            on_redirect=self._on_redirect,
            on_failure=self.on_failure,
            on_error=self.on_error,
            req_body=body,
            req_headers=headers,
            timeout=3,
            method='POST',
            debug=True,
        )

    def command_wheel(self, wheel_value):
        rpc_request = self.get_jrpc_request('wheel', {'value': wheel_value})
        self.send_rpc_request(rpc_request)

    def command_accell(self, accell_value):
        rpc_request = self.get_jrpc_request('accell', {'value': accell_value})
        self.send_rpc_request(rpc_request)

    def _on_success(self, request, result):
        print result

        try:
            result = json.loads(result)
        except Exception as e:
            self.update_error('RESPONSE INVALID')
            return

        if 'result' not in result:

            err_msg = 'UNKNOWN RESPONSE ERROR'

            if 'error' in result:
                if 'message' in result['error']:
                    err_msg = 'REQUEST INVALID'

            self.update_error(err_msg)

            return

        self.update_ok()

    def _on_redirect(self, request, result):
        self.update_error('REDIRECT ERROR')

    def on_failure(self, request, result):
        self.update_error('REQUEST FAILED')

    def on_error(self, request, result):
        self.update_error('REQUEST ERROR')

    def update_error(self, err_msg):
        with self.canvas.before:
            Color(0.5, 0, 0, mode='rgba')
            Rectangle(
                pos=[self.x, self.y],
                size=[self.width, self.height]
            )

        self.label.text = err_msg

    def update_ok(self):
        with self.canvas.before:
            Color(0, 0.5, 0, mode='rgba')
            Rectangle(
                pos=[self.x, self.y],
                size=[self.width, self.height]
            )

        self.label.text = 'OK'


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
    cmd_sender = ObjectProperty(None)

    def update_wheel(self, value):
        self.cmd_sender.command_wheel(value)


    def update_accell(self, value):
        self.cmd_sender.command_accell(value)


class RoverApp(App):
    def build(self):
        main_board = MainBoard()
        return main_board


if __name__ == '__main__':
    RoverApp().run()
