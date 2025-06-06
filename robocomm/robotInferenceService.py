from .service import BaseCommClient, BaseCommServer
from typing import Any, Dict
class RobotInferenceServer(BaseCommServer):
    """
    Server with three endpoints for real robot policies
    """

    def __init__(self, model, host: str = "*", port: int = 5555):
        super().__init__(host, port)
        self.register_endpoint("get_action", model.get_action)

class RobotInferenceClient(BaseCommClient):
    """
    Client for communicating with the RealRobotServer
    """

    def get_action(self, observations: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get the action from the server.
        The exact definition of the observations is defined
        by the policy, which contains the modalities configuration.
        """
        return self.call_endpoint("get_action", observations)
