from dataclasses import dataclass
from typing import Callable
import time
from logger import set_logger
from ..serialization.serialization import serialize, deserialize

import zmq

import threading


class BaseCommServer:
    """
    An inference server that spin up a ZeroMQ socket and listen for incoming requests.
    Can add custom endpoints by calling `register_endpoint`.
    """

    @dataclass
    class EndpointHandler:
        handler: Callable
        requires_input: bool = True

    def __init__(self, host: str = "*", port: int = 5555):
        self.logger = set_logger()
        self.logger.info("Starting server...")
        self.running = True
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)
        self.socket.bind(f"tcp://{host}:{port}")
        self._endpoints: dict[str, BaseCommServer.EndpointHandler] = {}

        # Register the ping endpoint by default
        self.register_endpoint("ping", self._handle_ping, requires_input=False)
        self.register_endpoint("kill", self._kill_server, requires_input=False)


    def _kill_server(self):
        """
        Kill the server.
        """
        self.running = False
        self.logger.info(f"Shutting down server...")
        return {"status": "ok", "message": "Server is shutting down"}

    def _handle_ping(self) -> dict:
        """
        Simple ping handler that returns a success message.
        """
        self.logger.info(f"Received ping request")
        return {"status": "ok", "message": "Server is running"}

    def register_endpoint(self, name: str, handler: Callable, requires_input: bool = True):
        """
        Register a new endpoint to the server.

        Args:
            name: The name of the endpoint.
            handler: The handler function that will be called when the endpoint is hit.
            requires_input: Whether the handler requires input data.
        """
        self.logger.info(f"Registering endpoint: {name}")
        self._endpoints[name] = BaseCommServer.EndpointHandler(handler, requires_input)

    def run(self):
        addr = self.socket.getsockopt_string(zmq.LAST_ENDPOINT)
        self.logger.info(f"Server is ready and listening on {addr}")
        while self.running:
            try:
                message = self.socket.recv()
                request = deserialize(message)
                endpoint = request.get("endpoint", "get_action")

                if endpoint not in self._endpoints:
                    raise ValueError(f"Unknown endpoint: {endpoint}")

                handler = self._endpoints[endpoint]
                result = (
                    handler.handler(request.get("data", {}))
                    if handler.requires_input
                    else handler.handler()
                )
                self.socket.send(serialize(result))
            except Exception as e:
                self.logger.error(f"Error in server: {e}")
                import traceback

                self.logger.error(traceback.format_exc())
                self.socket.send(b"ERROR")


class BaseCommClient:
    def __init__(self, host: str = "localhost", port: int = 5555, timeout_ms: int = 15000):
        self.logger = set_logger()
        self.context = zmq.Context()
        self.host = host
        self.port = port
        self.timeout_ms = timeout_ms
        self._init_socket()


    def _init_socket(self):
        """Initialize or reinitialize the socket with current settings"""
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(f"tcp://{self.host}:{self.port}")

    def ping(self) -> bool:
        try:
            ret = self.call_endpoint("ping", requires_input=False)
            print(f'ping return: {ret}')
            return True
        except zmq.error.ZMQError:
            self._init_socket()  # Recreate socket for next attempt
            return False

    def kill_server(self):
        """
        Kill the server.
        """
        self.call_endpoint("kill", requires_input=False)

    def call_endpoint(
            self, endpoint: str, data: dict | None = None, requires_input: bool = True
    ) -> dict:
        """
        Call an endpoint on the server.

        Args:
            endpoint: The name of the endpoint.
            data: The input data for the endpoint.
            requires_input: Whether the endpoint requires input data.
        """

        request: dict = {"endpoint": endpoint}
        if requires_input:
            request["data"] = data

        self.socket.send(serialize(request))
        message = self.socket.recv()
        if message == b"ERROR":
            self.logger.error(f"Error calling endpoint: {endpoint}")
            return {"status": "error", "message": "Error calling endpoint"}
        return deserialize(message)

    def __del__(self):
        """Cleanup resources on destruction"""
        self.socket.close()
        self.context.term()


class BasePublisher:
    def __init__(self, host: str = "localhost", port: int = 5555):
        self.logger = set_logger()
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)
        self.socket.bind(f"tcp://{host}:{port}")


    def publish(self, topic: str, message: dict):
        self.socket.send_multipart([topic.encode(), serialize(message)])
        # self.logger.info(f"Published message to topic {topic}: {message}")
        return {"status": "ok", "message": "Message published"}


class BaseSubscriber:
    def __init__(self, topic: str, callback: Callable, host: str = "localhost", port: int = 5555):
        self.logger = set_logger()
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.connect(f"tcp://{host}:{port}")
        self.socket.setsockopt_string(zmq.SUBSCRIBE, topic)
        self.running = True
        self.callback = callback
        self.thread = threading.Thread(target=self.run)


    def run(self):
        while self.running:
            topic, message = self.socket.recv_multipart()
            self.callback(deserialize(message))
            time.sleep(0.001)
        self.socket.close()
