from dnsproxy.domains import domain_matches, is_valid_domain_input, normalize_domain


def test_normalization_lowercase_and_final_dot():
    assert normalize_domain("ADS.Example.COM.") == "ads.example.com"


def test_input_validation_matches_pdf_rules():
    assert is_valid_domain_input("example.com")
    assert is_valid_domain_input("example.com.")
    assert is_valid_domain_input("a-b.123")
    assert not is_valid_domain_input("")
    assert not is_valid_domain_input(".example.com")
    assert not is_valid_domain_input("a..example.com")
    assert not is_valid_domain_input("bad domain.com")
    assert not is_valid_domain_input("faß.de")


def test_domain_matching_respects_label_boundary():
    assert domain_matches("example.com", "example.com")
    assert domain_matches("a.example.com", "example.com")
    assert not domain_matches("notexample.com", "example.com")
    assert not domain_matches("example.com.org", "example.com")
    assert not domain_matches("example.com", "a.example.com")
