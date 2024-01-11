# Copyright 2013-2023 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)
import pytest

from spack.extensions.scripting.functions import filter_specs
from spack.spec import Spec


@pytest.mark.db
@pytest.mark.extension('scripting')
@pytest.mark.usefixtures('database')
@pytest.mark.parametrize('kwargs,specs,expected', [
    ({"installed": None, "explicit": None}, ['boost', 'mpileaks'], ['boost', 'mpileaks']),
    ({"installed": True, "explicit": None},
     ['boost', 'mpileaks ^mpich', 'libelf'],
     ['mpileaks ^mpich', 'libelf']),
    ({"installed": False, "explicit": None},  ['boost', 'mpileaks^mpich', 'libelf'], ['boost']),
    ({"installed": True,  "explicit": True},  ['boost', 'mpileaks^mpich', 'libelf'], ['mpileaks ^mpich']),
    ({"installed": None,  "explicit": False}, ['boost', 'mpileaks^mpich', 'libelf'], ['boost', 'libelf']),
])
def test_filtering_specs(kwargs, specs, expected, default_mock_concretization):
    expected = [Spec(x) for x in expected]

    output = filter_specs(specs, **kwargs)
    output = [Spec(x.abstract) for x in output]

    for item in expected:
        assert item in output

    for item in set(Spec(x) for x in specs).difference(expected):
        assert item not in output
