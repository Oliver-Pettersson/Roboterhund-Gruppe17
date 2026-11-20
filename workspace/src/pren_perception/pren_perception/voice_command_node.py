"""
ROS-2-Node fuer Sprachbefehle: Mikrofon -> Vosk -> /pren/dog_command.

Veroeffentlicht:
    /pren/dog_command    pren_interfaces/DogCommand   (source = "voice")
    /pren/voice/level    std_msgs/Float32             Lautstaerke, zum Einstellen der Schwelle

Parameter:
    model_path           Ordner des Vosk-Modells (vosk-model-small-de-0.15)
    device               Index des Mikrofons, -1 = Standardgeraet
    volume_threshold     RMS-Schwelle des Rauschfilters
    min_confidence       Mindestsicherheit der Erkennung (0 bis 1)
    max_utterance_s      laengere Aeusserungen gelten als Gespraech und werden verworfen
    repeat_cooldown_s    so lange wird derselbe Befehl nicht erneut gesendet
"""

from pathlib import Path
import threading
import time

from pren_interfaces.msg import DogCommand
from pren_perception.voice.keyword_spotter import (
    RECOGNIZER_WORDS,
    RepeatFilter,
    VOICE_KEYWORDS,
)
from pren_perception.voice.microphone import Microphone
from pren_perception.voice.noise_gate import NoiseGate
from pren_perception.voice.voice_command_detector import VoiceCommandDetector
from pren_perception.voice.vosk_recognizer import VoskRecognizer
import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32

SAMPLE_RATE = 16000
CHUNK_SAMPLES = 1600   # 100 ms


class VoiceCommandNode(Node):
    """Hoert auf das Mikrofon und veroeffentlicht erkannte Befehle."""

    def __init__(self):
        super().__init__('voice_command')
        self.declare_parameter('model_path', '')
        self.declare_parameter('device', -1)
        self.declare_parameter('volume_threshold', 750.0)
        self.declare_parameter('hangover_chunks', 4)
        self.declare_parameter('pre_roll_chunks', 2)
        self.declare_parameter('repeat_cooldown_s', 1.5)
        self.declare_parameter('min_confidence', 0.7)
        self.declare_parameter('max_utterance_s', 2.0)

        model_path = Path(self.get_parameter('model_path').value)
        self.get_logger().info(f'Lade Vosk-Modell {model_path} ...')
        self._detector = VoiceCommandDetector(
            recognizer=VoskRecognizer(model_path, SAMPLE_RATE, RECOGNIZER_WORDS),
            gate=NoiseGate(threshold=self.get_parameter('volume_threshold').value,
                           hangover_chunks=self.get_parameter('hangover_chunks').value,
                           pre_roll_chunks=self.get_parameter('pre_roll_chunks').value),
            repeat_filter=RepeatFilter(self.get_parameter('repeat_cooldown_s').value),
            min_confidence=self.get_parameter('min_confidence').value,
            max_utterance_s=self.get_parameter('max_utterance_s').value,
        )

        device = self.get_parameter('device').value
        self._microphone = Microphone(SAMPLE_RATE, CHUNK_SAMPLES,
                                      device=None if device < 0 else device)

        self._command_pub = self.create_publisher(DogCommand, '/pren/dog_command', 10)
        self._level_pub = self.create_publisher(Float32, '/pren/voice/level', 10)

        self._running = True
        self._microphone.start()
        self._worker = threading.Thread(target=self._listen, daemon=True)
        self._worker.start()
        self.get_logger().info(
            f'Hoere auf {self._microphone.device_name}: {", ".join(VOICE_KEYWORDS)}')

    def _listen(self) -> None:
        while self._running and rclpy.ok():
            chunk = self._microphone.read(timeout_s=0.1)
            if chunk is None:
                continue
            command = self._detector.process(chunk, time.monotonic())
            self._level_pub.publish(Float32(data=self._detector.last_level))
            if command is not None:
                self._publish(command)

    def _publish(self, command) -> None:
        msg = DogCommand(command=int(command), source=DogCommand.SOURCE_VOICE, confidence=1.0)
        msg.header.stamp = self.get_clock().now().to_msg()
        self._command_pub.publish(msg)
        self.get_logger().info(f'Sprachbefehl erkannt: {command.name}')

    def destroy_node(self):
        """Stoppt Mikrofon und Hintergrund-Thread."""
        self._running = False
        self._worker.join(timeout=1.0)
        self._microphone.stop()
        super().destroy_node()


def main(args=None):
    """Startet den voice_command-Node."""
    rclpy.init(args=args)
    node = VoiceCommandNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
