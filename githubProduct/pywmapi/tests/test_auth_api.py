import os
from typing import Dict, Optional

import pytest

from pywmapi.auth.api import *


@pytest.mark.skip("No third-party support for sign-in in API")
def get_test_signin_dict() -> Optional[Dict[str, str]]:
    email = os.getenv("TEST_WM_EMAIL")
    password = os.getenv("TEST_WM_PASSWORD")
    if email is not None and password is not None:
        return {
            "email": email,
            "password": password,
        }
    else:
        return None


@pytest.mark.skip("No third-party support for sign-in in API")
def test_jwt():
    get_jwt_token()


@pytest.mark.skip("No third-party support for sign-in in API")
def test_login():
    d = get_test_signin_dict()
    _sess = signin(**d)
