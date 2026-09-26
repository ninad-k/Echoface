from echoface.util.text import normalize_for_speech, number_to_words, word_count


def test_number_to_words_basic():
    assert number_to_words("5") == "five"
    assert number_to_words("21") == "twenty-one"
    assert number_to_words("100") == "one hundred"
    assert number_to_words("1234") == "one thousand two hundred thirty-four"


def test_currency():
    assert normalize_for_speech("$5") == "five dollars"
    assert normalize_for_speech("$1") == "one dollar"
    assert normalize_for_speech("$5.50") == "five dollars and fifty cents"


def test_percent():
    assert normalize_for_speech("23%") == "twenty-three percent"


def test_abbreviations():
    out = normalize_for_speech("Dr. Smith vs. Mr. Jones, etc.")
    assert "doctor" in out.lower()
    assert "versus" in out.lower()
    assert "mister" in out.lower()
    assert "et cetera" in out.lower()


def test_symbols():
    out = normalize_for_speech("Tom & Jerry @ home")
    assert "and" in out
    assert "at" in out


def test_plain_numbers_in_sentence():
    out = normalize_for_speech("I have 3 apples and 12 oranges.")
    assert "three apples" in out
    assert "twelve oranges" in out


def test_word_count():
    assert word_count("hello world") == 2
    assert word_count("") == 0
    assert word_count("  a   b  c ") == 3


def test_normalize_idempotent_on_plain_text():
    text = "This is a normal sentence with no numbers."
    assert normalize_for_speech(text) == text
