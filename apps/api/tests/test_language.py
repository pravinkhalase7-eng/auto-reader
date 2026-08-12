import pytest

from app.utils.languages import detect_script_language


def test_detect_english():
    assert detect_script_language("The lion was sleeping in the forest.") == "en"


def test_detect_hindi():
    assert detect_script_language("शेर और चूहा जंगल में रहते थे। चूहे ने मदद की।") == "hi"


def test_detect_marathi():
    assert detect_script_language("सिंह आणि उंदीर जंगलात आहे. उंदराने मदत केली.") == "mr"
