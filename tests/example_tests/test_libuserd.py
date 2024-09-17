import pytest

from ansys.pyensight.core.libuserd import LibUserd

def test_libuserd_basic(tmpdir, pytestconfig: pytest.Config):
    data_dir = tmpdir.mkdir("datadir")
    use_local = pytestconfig.getoption("use_local_launcher")
    if use_local:
        libuserd = LibUserd()
    else:
        libuserd = LibUserd(use_docker=True, use_dev=True, data_directory=data_dir)
    libuserd.initialize()
    libuserd.get_all_readers()
    libuserd.ansys_release_number()
    libuserd.ansys_release_string()
    cas_file = libuserd.download_pyansys_example("mixing_elbow.cas.h5","pyfluent/mixing_elbow")
    dat_file = libuserd.download_pyansys_example("mixing_elbow.dat.h5","pyfluent/mixing_elbow")
    r = libuserd.query_format(cas_file, dat_file)
    d = r[0].read_dataset(cas_file, dat_file)
    
    parts = d.parts()
    p = [p for p in parts if p.name == "elbow-fluid"][0]

    vars = d.variables()
    v = [v for v in vars if v.name == "Static_Pressure"][0]
    
    p.nodes()
    p.num_elements()
    p.element_conn(libuserd.ElementType.HEX08)
    p.variable_values(v, libuserd.ElementType.HEX08)
    
    libuserd.shutdown()
