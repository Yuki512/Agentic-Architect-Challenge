from io import StringIO
import json
import logging
import unittest

from document_agent.observability import JsonEventFormatter, log_event


class ObservabilityTests(unittest.TestCase):
    def test_log_event_writes_machine_readable_json(self):
        output = StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(JsonEventFormatter())
        logger = logging.getLogger("part3-observability-test")
        logger.handlers = [handler]
        logger.propagate = False
        logger.setLevel(logging.INFO)

        log_event(
            logger,
            logging.INFO,
            "agent_turn_completed",
            request_id="request-1",
            latency_ms=125,
            tool_count=1,
        )
        payload = json.loads(output.getvalue())

        self.assertEqual(payload["event"], "agent_turn_completed")
        self.assertEqual(payload["request_id"], "request-1")
        self.assertEqual(payload["latency_ms"], 125)
        self.assertEqual(payload["tool_count"], 1)
        self.assertIn("timestamp", payload)

    def test_event_contains_no_unrequested_message_field(self):
        record = logging.LogRecord(
            "document_agent.agent",
            logging.ERROR,
            __file__,
            1,
            "agent_turn_failed",
            (),
            None,
        )
        record.event_name = "agent_turn_failed"
        record.event_fields = {
            "request_id": "request-2",
            "error_type": "TimeoutError",
        }

        payload = json.loads(JsonEventFormatter().format(record))

        self.assertNotIn("message", payload)
        self.assertNotIn("api_key", payload)
        self.assertNotIn("prompt", payload)


if __name__ == "__main__":
    unittest.main()
