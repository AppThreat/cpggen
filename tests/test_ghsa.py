import json
import os

import pytest

from cpggen.source import ghsa


# A pytest fixture that returns the test data file path
@pytest.fixture
def test_data():
    return os.path.join(
        os.path.dirname(os.path.realpath(__file__)), "data", "ghsa-data.json"
    )


# Test function for the 'parse_response' function in the ghsa module
def test_parse(test_data):
    with open(test_data) as fp:
        purl_list = ghsa.parse_response(json.load(fp))
        assert len(purl_list) == 25
        assert purl_list == [
            # List of expected outputs
            {
                "ghsaId": "GHSA-9jxw-cfrh-jxq6",
                "purl": "pkg:composer/cachethq/cachet@2.5.1",
            },
            {
                "ghsaId": "GHSA-f865-m6cq-j9vx",
                "purl": "pkg:pypi/mpmath@1.3.0",
            },
            {
                "ghsaId": "GHSA-2c7v-qcjp-4mg2",
                "purl": "pkg:nuget/microsoft.windowsdesktop.app.runtime.win-x64@7.0.1",
            },
            {
                "ghsaId": "GHSA-2c7v-qcjp-4mg2",
                "purl": "pkg:nuget/microsoft.windowsdesktop.app.runtime.win-x86@7.0.1",
            },
            {
                "ghsaId": "GHSA-2c7v-qcjp-4mg2",
                "purl": "pkg:nuget/microsoft.windowsdesktop.app.runtime.win-arm64@7.0.1",
            },
            {
                "ghsaId": "GHSA-2c7v-qcjp-4mg2",
                "purl": "pkg:nuget/microsoft.windowsdesktop.app.runtime.win-x86@6.0.12",
            },
            {
                "ghsaId": "GHSA-2c7v-qcjp-4mg2",
                "purl": "pkg:nuget/microsoft.windowsdesktop.app.runtime.win-x64@6.0.12",
            },
            {
                "ghsaId": "GHSA-2c7v-qcjp-4mg2",
                "purl": "pkg:nuget/microsoft.windowsdesktop.app.runtime.win-arm64@6.0.12",
            },
            {
                "ghsaId": "GHSA-2c7v-qcjp-4mg2",
                "purl": "pkg:nuget/microsoft.windowsdesktop.app.runtime.win-x86@3.1.32",
            },
            {
                "ghsaId": "GHSA-2c7v-qcjp-4mg2",
                "purl": "pkg:nuget/microsoft.windowsdesktop.app.runtime.win-x64@3.1.32",
            },
            {
                "ghsaId": "GHSA-7mvr-5x2g-wfc8",
                "purl": "pkg:gem/bootstrap@4.1.2",
            },
            {
                "ghsaId": "GHSA-w9vv-q986-vj7x",
                "purl": "pkg:cargo/uu_od@0.0.4",
            },
            {
                "ghsaId": "GHSA-vwjc-q9px-r9vq",
                "purl": "pkg:npm/ecstatic@1.4.0",
            },
            {
                "ghsaId": "GHSA-f683-35w9-28g5",
                "purl": "pkg:composer/fixpunkt/fp-newsletter@1.1.1",
            },
            {
                "ghsaId": "GHSA-f683-35w9-28g5",
                "purl": "pkg:composer/fixpunkt/fp-newsletter@2.1.2",
            },
            {
                "ghsaId": "GHSA-f683-35w9-28g5",
                "purl": "pkg:composer/fixpunkt/fp-newsletter@3.2.6",
            },
            {
                "ghsaId": "GHSA-98g7-rxmf-rrxm",
                "purl": "pkg:maven/io.fabric8/kubernetes-client@5.11.2",
            },
            {
                "ghsaId": "GHSA-98g7-rxmf-rrxm",
                "purl": "pkg:maven/io.fabric8/kubernetes-client@5.10.2",
            },
            {
                "ghsaId": "GHSA-98g7-rxmf-rrxm",
                "purl": "pkg:maven/io.fabric8/kubernetes-client@5.8.1",
            },
            {
                "ghsaId": "GHSA-98g7-rxmf-rrxm",
                "purl": "pkg:maven/io.fabric8/kubernetes-client@5.7.4",
            },
            {
                "ghsaId": "GHSA-98g7-rxmf-rrxm",
                "purl": "pkg:maven/io.fabric8/kubernetes-client@5.3.2",
            },
            {
                "ghsaId": "GHSA-98g7-rxmf-rrxm",
                "purl": "pkg:maven/io.fabric8/kubernetes-client@5.1.2",
            },
            {
                "ghsaId": "GHSA-98g7-rxmf-rrxm",
                "purl": "pkg:maven/io.fabric8/kubernetes-client@5.0.3",
            },
            {
                "ghsaId": "GHSA-v9j4-cp63-qv62",
                "purl": "pkg:golang/github.com/gen2brain/go-unarr@0.1.4",
            },
            {
                "ghsaId": "GHSA-h7wm-ph43-c39p",
                "purl": "pkg:pypi/scrapy@2.9.0",
            },
        ]
