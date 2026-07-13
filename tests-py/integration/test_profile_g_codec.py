import json
from pathlib import Path
import pytest
from validators.profile_g import *
V=Path(__file__).parents[2]/"conformance"/"vectors"
def load(n):return json.loads((V/n).read_text())["cases"]
@pytest.mark.parametrize("x",load("profile_g_artifacts_valid.json"),ids=lambda x:x["id"])
def test_valid(x):assert validate_profile_g_artifact(x["kind"],x["payload"],x.get("negotiated_limits"))==x["expected_cid"]
@pytest.mark.parametrize("x",load("profile_g_artifacts_invalid.json"),ids=lambda x:x["id"])
def test_invalid(x):
 with pytest.raises(ProfileGValidationError) as e:validate_profile_g_artifact(x["kind"],x["payload"],x.get("negotiated_limits"))
 assert(e.value.code,e.value.path)==(x["expected_error"],x["expected_path"])
