#!/usr/bin/env python3
import asyncio
import serial
import json
import logging
import asyncio
import websockets
import aioserial
import os

serial_queue = asyncio.Queue()
api_queue = asyncio.Queue()

class Btn:
    def __init__(self, num, label, x, y, width, domain, entity_id):
        self.num = num
        self.label = label
        self.x = x
        self.y = y
        self.width = width
        self.state = False
        self.domain = domain
        self.entity_id = entity_id

    def display_data(self):
        return {
                "widget": "btn",
                "num": self.num,
                "label": self.label,
                "x": self.x,
                "y": self.y,
                "width": self.width,
                "state": self.state,
        }

    async def click(self, api):
        await api.put({
            "type": "call_service",
            "domain": self.domain,
            "service": "toggle",
            "service_data": {
                "entity_id": self.entity_id,
            }
        })

buttons = [
    Btn(num=0, label="bedroom", x=60, y=200, width=100, domain="light", entity_id="light.bedroom_light"),
    Btn(num=1, label="PC", x=160, y=200, width=60, domain="switch", entity_id="switch.desktop"),
]

async def api_task():
    url = os.environ['HASS_SERVER']
    if url.startswith('https://'):
        uri = f'wss://{url.replace("https://", "")}/api/websocket'
    else:
        uri = f'wss://{url.replace("http://", "")}/api/websocket'

    while True:
        try:
            async with websockets.connect(uri) as websocket:
                logging.info("Connected to WS API")
                await websocket.send(json.dumps({
                    'type': 'auth',
                    'access_token': os.environ['HASS_TOKEN'], 
                }))

                async def update_entity(entity_id, state):
                    if entity_id == 'sensor.time':
                        await serial_queue.put({
                            'widget': 'time',
                            'state': state['state'],
                        })
                    else:
                        for btn in buttons:
                            if btn.entity_id == entity_id:
                                btn.state = state['state'] == 'on'
                                await serial_queue.put(btn.display_data())


                async def update_entities(data):
                    for item in data['result']:
                        await update_entity(item['entity_id'], item)


                await api_queue.put({'type': 'subscribe_events', 'event_type': 'state_changed'})
                await api_queue.put(({"type": "get_states"}, update_entities))

                callbacks = {}

                async def reader():
                    while True:
                        message = await websocket.recv()
                        if message is None:
                            break
                        logging.info(f"received from api: {message}")

                        message = json.loads(message)
                        if message['type'] == 'event':
                            d = message['event']['data']
                            await update_entity(d["entity_id"], d["new_state"])
                        elif message['type'] == 'result':
                            cb = callbacks.get(message['id'], None)
                            if cb:
                                await cb(message)

                async def writer():
                    cmd_id = 3
                    while True:
                        data = await api_queue.get()
                        if isinstance(data, tuple):
                            callbacks[cmd_id] = data[1]
                            data = data[0]

                        data["id"] = cmd_id
                        logging.info(f"sending to api: {data}")
                        await websocket.send(json.dumps(data))
                        cmd_id += 1
                await asyncio.gather(reader(), writer())
        except websockets.exceptions.WebSocketException as e:
            logging.exception(e)
            await asyncio.sleep(1)

async def serial_task():
    while True:
        try:
            s = aioserial.AioSerial(port='/dev/serial/by-id/usb-Arduino__www.arduino.cc__0043_852313632363511042C1-if00', baudrate=115200)
            logging.info("Connected to serial")

            done = asyncio.Event()

            async def reader():
                while True:
                    l = await s.readline_async()
                    logging.info(f"serial received: {l}")
                    # {"id":30,"type":"call_service","domain":"light","service":"toggle","service_data":{"entity_id":"light.bedroom_light"}}
                    msg = json.loads(l)

                    action = msg.get('type', None)
                    if action == 'ack':
                        done.set()
                    elif action == 'reset':
                        done.set()
                    elif action == 'btn_click':
                        widget = buttons[msg["num"]]
                        await widget.click(api_queue)

                    else:
                        logging.error(f"Unknown type: {action}")

                    #await api_queue.put(json.loads(l))


            async def writer():
                while True:
                    data = await serial_queue.get()
                    await done.wait()
                    logging.info(f"sending to serial: {data}")
                    s.write(json.dumps(data).encode('utf-8'))
                    s.write(b"\n")
                    done.clear()


            await asyncio.gather(reader(), writer())
        except serial.serialutil.SerialException as e:
            logging.exception(e)
            await asyncio.sleep(1)

logging.basicConfig(level=logging.INFO)

loop = asyncio.get_event_loop()
loop.create_task(api_task())
loop.create_task(serial_task())
loop.run_forever()
