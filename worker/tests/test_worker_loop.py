"""D-00-09: worker long-polls q_verify with vt=300 at call site."""
import pytest


@pytest.mark.xfail(strict=False, reason="Wave 4 pending — dispatcher not yet implemented")
def test_dispatcher_uses_vt_300():
    raise NotImplementedError(
        "Wave 4: import dispatcher; assert read_with_poll called with vt=300"
    )
