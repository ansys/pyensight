from ansys.pyensight.core.libuserd import LibUserd
import numpy
import pytest


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
    cas_file = libuserd.download_pyansys_example("mixing_elbow.cas.h5", "pyfluent/mixing_elbow")
    dat_file = libuserd.download_pyansys_example("mixing_elbow.dat.h5", "pyfluent/mixing_elbow")
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


def test_libuserd_synthetic_time(tmpdir, pytestconfig: pytest.Config):
    data_dir = tmpdir.mkdir("datadir")
    use_local = pytestconfig.getoption("use_local_launcher")
    if use_local:
        libuserd = LibUserd()
    else:
        libuserd = LibUserd(use_docker=True, use_dev=True, data_directory=data_dir)
    libuserd.initialize()
    opt = {
        "Long names": 0,
        "Number of timesteps": 10,
        "Number of scalars": 3,
        "Number of spheres": 10,
        "Number of cubes": 10,
    }
    d = libuserd.load_data("foo", file_format="Synthetic", reader_options=opt)
    p = d.parts()[0]
    v = d.variables()[0]

    assert "Sphere" in p.name
    assert "Scalar" in v.name
    assert len(d.timevalues()) == 10
    assert d.get_number_of_time_sets() == 1

    d.set_timestep(5)
    n = p.nodes()
    n.shape = (len(n) // 3, 3)
    centroid_5 = numpy.average(n, 0)

    d.set_timestep(0)
    n = p.nodes()
    n.shape = (len(n) // 3, 3)
    centroid_0 = numpy.average(n, 0)

    d.set_timevalue(5.0)
    n = p.nodes()
    n.shape = (len(n) // 3, 3)
    centroid_50 = numpy.average(n, 0)

    assert numpy.array_equal(centroid_5, centroid_50)
    assert not numpy.array_equal(centroid_5, centroid_0)

    libuserd.shutdown()