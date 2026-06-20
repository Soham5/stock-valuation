from stockval.validation import ERROR, WARN, validate_company


def test_clean_company_has_no_errors(sample_company):
    report = validate_company(sample_company)
    assert report.is_usable
    assert not report.errors


def test_negative_price_is_error(sample_company):
    from dataclasses import replace

    sample_company.market = replace(sample_company.market, price=-5.0)
    report = validate_company(sample_company)
    assert not report.is_usable
    assert any(i.field == "market.price" and i.severity == ERROR for i in report.errors)


def test_ebitda_below_ebit_is_error(sample_company):
    from dataclasses import replace

    sample_company.financials = replace(sample_company.financials, ebitda=1.0, ebit=10.0)
    report = validate_company(sample_company)
    assert any(i.field == "financials.ebitda" and i.severity == ERROR for i in report.errors)


def test_out_of_range_tax_rate_is_warning(sample_company):
    from dataclasses import replace

    sample_company.financials = replace(sample_company.financials, tax_rate=0.9)
    report = validate_company(sample_company)
    assert any(i.field == "financials.tax_rate" and i.severity == WARN for i in report.warnings)


def test_market_cap_mismatch_warns(sample_company):
    from dataclasses import replace

    # price*shares = 100 * 1e6 = 1e8; set market cap far away.
    sample_company.market = replace(sample_company.market, market_cap=5e8)
    report = validate_company(sample_company)
    assert any(i.field == "market.market_cap" for i in report.warnings)
