from enum import Enum

import numpy as np


def print_userd_info(userd):
    print(f"Userd lib version: {userd.library_version()}")
    print(f"ANSYS release name: {userd.ansys_release_string()}")
    print(f"ANSYS release number: {userd.ansys_release_number()}")


def read_dataset(userd, file_1, file_2):
    readers = userd.query_format(file_1, file_2)
    if not readers:
        print("No suitable readers found for the dataset.")
        return
    reader = readers[0]
    print(f"Selected reader = {reader.name}")
    dataset = reader.read_dataset(file_1, file_2)
    return dataset


def extract_data(dataset):
    parts = dataset.parts()
    variables = dataset.variables()
    max_time_steps = len(dataset.timevalues())

    # useful for debugging
    # print(f"Number of timesteps = {max_time_steps}")
    # print(parts)
    # print(variables)
    return parts, variables, max_time_steps


def process_variables(timestep, dataset, parts, variables):
    Scalar = 1
    Vector = 2
    Elemental = 3

    if timestep >= 0:
        dataset.set_timestep(timestep)

    # This map will store concatenated values across all parts for each var.id
    var_data_map = {}

    # This map will store values separately for each part and var.id (without concatenation)
    part_var_data_map = {}

    for part in parts:
        part_id = part.id  # Get the part ID

        for var in variables:
            eleList = []

            # Check if the variable is Elemental or Nodal
            if var.location == Elemental:
                elements = part.num_elements()  # Get element types and counts
                eleList = list(elements.keys())  # Populate eleList with element types
            else:
                eleList = [0]  # Handle Nodal or Part/Case Constant cases

            var_values = None

            # Initialize an empty array to store concatenated values for elemental variables
            all_elemental_vars = []

            # Loop over element types
            for etype in eleList:
                try:
                    # Retrieve values based on variable type (Scalar or Vector)
                    if var.type == Scalar:
                        var_values = np.array(part.variable_values(var, etype))
                    elif var.type == Vector:
                        var_values_0 = np.array(part.variable_values(var, etype, 0))
                        var_values_1 = np.array(part.variable_values(var, etype, 1))
                        var_values_2 = np.array(part.variable_values(var, etype, 2))
                        var_values = np.column_stack((var_values_0, var_values_1, var_values_2))

                    # If the variable is elemental, concatenate the values for all element types
                    if var.location == Elemental and var_values is not None:
                        all_elemental_vars.append(var_values)

                except Exception as e:
                    print(
                        f"Error retrieving values for variable '{var.name}' in part '{part.name}': {e}"
                    )
                    continue

            # Handle the case where it's elemental by concatenating all the element types
            if var.location == Elemental:
                if all_elemental_vars:
                    var_values = np.concatenate(all_elemental_vars, axis=0)

            # Process nodal or elemental variables if applicable
            if var_values is not None:
                var_id = var.id  # Use var.id as the key

                # Handle concatenated map (var_data_map)
                if var_id in var_data_map:
                    var_data_map[var_id]["values"] = np.concatenate(
                        (var_data_map[var_id]["values"], var_values), axis=0
                    )
                else:
                    var_data_map[var_id] = {"name": var.name, "values": var_values}

                # Handle part-specific map (part_var_data_map) without concatenation
                if part_id not in part_var_data_map:
                    part_var_data_map[part_id] = {}

                if var_id in part_var_data_map[part_id]:
                    part_var_data_map[part_id][var_id]["values"] = np.concatenate(
                        (part_var_data_map[part_id][var_id]["values"], var_values), axis=0
                    )
                else:
                    part_var_data_map[part_id][var_id] = {"name": var.name, "values": var_values}

    return var_data_map, part_var_data_map


def precompute_all_timesteps(dataset, parts, variables, max_time_steps):
    timestep_cache = {}  # This will hold the concatenated var_data_map for each timestep
    part_var_cache = {}  # This will hold the part-specific part_var_data_map for each timestep

    # Determine if we are dealing with static (max_time_steps == 0) or dynamic simulation
    if max_time_steps == 0:
        timesteps = [-1]  # Static case: use timestep = -1 for special handling
    else:
        timesteps = range(max_time_steps)  # Dynamic case: loop over 0 to max_time_steps - 1

    # Generalized loop for both static and dynamic cases
    for timestep in timesteps:
        if timestep >= 0:
            print(f"Reading variables data for timestep {timestep}...")

        # Get both concatenated and part-specific maps from process_variables
        var_data_map, part_var_data_map = process_variables(timestep, dataset, parts, variables)

        # Handle NaN values in var_data_map (concatenated data across all parts)
        for var_id, data in var_data_map.items():
            data["values"] = np.nan_to_num(data["values"], nan=0.0)

        # Handle NaN values in part_var_data_map (part-specific data)
        for part_id, var_dict in part_var_data_map.items():
            for var_id, data in var_dict.items():
                data["values"] = np.nan_to_num(data["values"], nan=0.0)

        # Always store the result in timestep_cache and part_var_cache using the timestep
        timestep_cache[timestep if timestep != -1 else 0] = var_data_map
        part_var_cache[timestep if timestep != -1 else 0] = part_var_data_map

    print("Reading complete!")

    # Return both maps: concatenated timestep_cache and part_var_cache
    return timestep_cache, part_var_cache


def get_all_userd_data(userd, file_1, file_2=None):
    # print userd basic info
    print_userd_info(userd)

    # Read dataset
    dataset = read_dataset(userd, file_1, file_2)

    # Extract data
    parts, variables, max_time_steps = extract_data(dataset)

    # Precompute all timesteps
    timestep_cache, part_var_cache = precompute_all_timesteps(
        dataset, parts, variables, max_time_steps
    )

    # Shutdown userd
    userd.shutdown()
    print("Userd shutdown complete.")

    return parts, variables, max_time_steps, timestep_cache, part_var_cache


def get_all_pyensight_data(session, file_1, file_2):
    # Initialize and configure pyensight
    core = session.ensight.objs.core

    # load all the data
    session.load_data(file_1, file_2)

    # Get parts and variables
    parts = core.PARTS
    variables = core.VARIABLES

    return parts, variables


def get_var_type_and_complexity(vartype):
    # Define the Ensight VARTYPEENUM constants using Enum
    class ENSIGHTVARTYPEENUM(Enum):
        SCALAR = 0
        VECTOR = 1
        TENSOR = 2
        SCALAR_COMPLEX = 3
        VECTOR_COMPLEX = 4
        CONSTANT = 5
        TIME_FUNC = 6
        COORDS = 7
        CONSTANT_PER_PART = 8
        UNKNOWN = 9

    # Initialize the default return values
    is_complex = False  # Default to False (real)

    # Map the integer vartype to the corresponding VARTYPEENUM and handle comparison
    if vartype in (ENSIGHTVARTYPEENUM.CONSTANT.value, ENSIGHTVARTYPEENUM.CONSTANT_PER_PART.value):
        var_type = 0  # Constant
    elif vartype == ENSIGHTVARTYPEENUM.SCALAR.value:
        var_type = 1  # Scalar
    elif vartype == ENSIGHTVARTYPEENUM.VECTOR.value:
        var_type = 2  # Vector
    elif vartype == ENSIGHTVARTYPEENUM.TENSOR.value:
        var_type = 3  # Tensor
    elif vartype == ENSIGHTVARTYPEENUM.SCALAR_COMPLEX.value:
        var_type = 1  # Scalar complex, but still scalar
        is_complex = True  # Mark as complex
    elif vartype == ENSIGHTVARTYPEENUM.VECTOR_COMPLEX.value:
        var_type = 2  # Vector complex, but still vector
        is_complex = True  # Mark as complex
    elif vartype in (
        ENSIGHTVARTYPEENUM.TIME_FUNC.value,
        ENSIGHTVARTYPEENUM.COORDS.value,
        ENSIGHTVARTYPEENUM.UNKNOWN.value,
    ):
        var_type = -1  # Unknown or unsupported

    return var_type, is_complex


def _test_parts(part_userd, part_ensight):
    failures = []

    # Compare the number of parts in each list
    try:
        assert len(part_userd) == len(
            part_ensight
        ), f"Number of parts do not match: {len(part_userd)} vs {len(part_ensight)}"
    except AssertionError as e:
        failures.append(str(e))

    # Compare each part in the lists
    for userd_part, ensight_part in zip(part_userd, part_ensight):
        try:
            assert (
                userd_part.id == ensight_part.partnumber
            ), f"Part IDs do not match: {userd_part.id} vs {ensight_part.partnumber}"
        except AssertionError as e:
            failures.append(str(e))

        try:
            assert (
                userd_part.name == ensight_part.DESCRIPTION
            ), f"Part names do not match: {userd_part.name} vs {ensight_part.DESCRIPTION}"
        except AssertionError as e:
            failures.append(str(e))

    # Return the list of failures and error code
    return failures, 0 if not failures else 1


def normalize_string(input_string):
    # Replace underscores with spaces and strip extra spaces, then convert to lowercase for case-insensitive comparison.
    return input_string.replace("_", " ").strip().lower()


def get_userd_values(userd_part_var_timestep_cache, timestep, part_id, var_id):
    """
    Safely retrieve userd values from the cache based on timestep, part_id, and var_id.

    Args:
        userd_part_var_timestep_cache (dict): The main cache with all timesteps, parts, and variables.
        timestep (int): The timestep to retrieve data for.
        part_id (int): The part ID to retrieve data for.
        var_id (int): The variable ID to retrieve data for.

    Returns:
        np.array or None: The userd variable values if found, otherwise None.
    """
    # Check if timestep exists in the cache
    userd_part_var_value_dictionary = userd_part_var_timestep_cache.get(timestep)

    # If the timestep does not exist, return None
    if not userd_part_var_value_dictionary:
        return None

    # Check if part_id exists in the part variable value dictionary
    part_data = userd_part_var_value_dictionary.get(part_id)

    # If the part_id does not exist, return None
    if not part_data:
        return None

    # Check if var_id exists in the part data
    variable_data = part_data.get(var_id)

    # If the var_id does not exist, return None
    if not variable_data:
        return None

    # Ensure 'values' key exists in the variable_data dictionary
    userd_values = variable_data.get("values")

    # If values are not present, return None
    if userd_values is None:
        return None

    return userd_values


def _test_variable_values(
    parts_userd,
    parts_ensight,
    variables_userd,
    variables_ensight,
    userd_part_var_timestep_cache,
    timestep,
):
    failures = []
    Scalar = 1

    # Create a dictionary mapping (id, normalized name) to variables & parts for pyensight
    ensight_var_dict = {
        (var.id, normalize_string(var.DESCRIPTION)): var for var in variables_ensight
    }
    ensight_part_dict = {(part.PARTNUMBER, part.DESCRIPTION): part for part in parts_ensight}

    # loop over userd parts
    for userd_var in variables_userd:
        if (
            userd_var.type != Scalar
        ):  # ToDo: we only do the comparisons for scalar variables; We will expand this for other types
            continue

        var_id = userd_var.id
        norm_name = normalize_string(userd_var.name)

        # Find the corresponding variable in ensight_dict by ID and normalized name
        ensight_var = ensight_var_dict.get((var_id, norm_name))

        # If there's no exact match by ID and name, attempt a name-based fallback
        if not ensight_var:
            ensight_var = next(
                (
                    e_var
                    for (e_id, e_name), e_var in ensight_var_dict.items()
                    if e_name == norm_name
                ),
                None,
            )

        if not ensight_var:
            failures.append(
                f"Variable with ID {var_id} and name '{userd_var.name}' is missing in ensight variables."
            )
            continue

        for userd_part in parts_userd:
            part_id = userd_part.id
            part_name = userd_part.name

            # Find the corresponding part in ensight_part_dict by ID and name
            ensight_part = ensight_part_dict.get((part_id, part_name))

            # If there's no exact match by ID and name, attempt a Id or name based fallback
            if not ensight_part:
                ensight_part = next(
                    (
                        e_part
                        for (e_id, e_name), e_part in ensight_part_dict.items()
                        if e_id == part_id or e_name == part_name
                    ),
                    None,
                )

            if not ensight_part:
                failures.append(
                    f"Part with ID {part_id} and name '{part_name}' is missing in ensight part list."
                )
                continue

            # Retrieve values from the dictionaries (safely as not all variables are defined for all parts)
            userd_values = get_userd_values(
                userd_part_var_timestep_cache, timestep, part_id, var_id
            )
            # If no values are found, continue to the next iteration
            if userd_values is None:
                continue

            ensight_values = ensight_part.get_values([ensight_var], activate=1)[ensight_var]

            # First, compare the lengths of the arrays
            if len(userd_values) != len(ensight_values):
                failures.append(
                    f"Array lengths do not match for Part {part_id} and variable '{userd_var.name}': "
                    f"Userd length = {len(userd_values)}, Ensight length = {len(ensight_values)}"
                )
            else:
                # Lengths match, so compare individual values using np.allclose
                try:
                    if not np.allclose(userd_values, ensight_values):
                        # Find specific differences in individual elements
                        differences = np.where(~np.isclose(userd_values, ensight_values))[0]
                        for diff_idx in differences:
                            failures.append(
                                f"Value mismatch at index {diff_idx} for Part {part_id} and variable '{userd_var.name}': "
                                f"Userd value = {userd_values[diff_idx]}, Ensight value = {ensight_values[diff_idx]}"
                            )
                except Exception as e:
                    failures.append(
                        f"Error comparing values for Part ID {part_id} and variable '{userd_var.name}': {str(e)}"
                    )

    # Return the list of failures and error code
    return failures, 0 if not failures else 1


# Create a method to map PyEnsight variable location to userd variable location
def map_to_userd_variable_location(value):
    # Define the Userd VariableLocation enum class
    class UserdVariableLocation(Enum):
        DATASET = 0
        PART = 1
        NODE = 2
        ELEMENT = 3
        UNKNOWN_LOCATION = -1

    mapping = {
        8: UserdVariableLocation.DATASET,  # ENS_VAR_CASE
        9: UserdVariableLocation.PART,  # ENS_VAR_CONSTANT_PER_PART
        1: UserdVariableLocation.ELEMENT,  # ENS_VAR_ELEM
        2: UserdVariableLocation.NODE,  # ENS_VAR_NODE
    }

    # Return the corresponding enum value, or UNKNOWN_LOCATION if not found
    return mapping.get(value, UserdVariableLocation.UNKNOWN_LOCATION)


def _test_variables(variables_userd, variables_ensight):
    failures = []

    # Create a dictionary mapping (id, normalized name) to variables for pyensight
    ensight_dict = {(var.id, normalize_string(var.DESCRIPTION)): var for var in variables_ensight}

    # Iterate only over userd variables
    for userd_var in variables_userd:
        var_id = userd_var.id
        norm_name = normalize_string(userd_var.name)

        # Find the corresponding variable in ensight_dict by ID and normalized name
        ensight_var = ensight_dict.get((var_id, norm_name))

        # If there's no exact match by ID and name, attempt a name-based fallback
        if not ensight_var:
            ensight_var = next(
                (e_var for (e_id, e_name), e_var in ensight_dict.items() if e_name == norm_name),
                None,
            )

        if not ensight_var:
            failures.append(
                f"Variable with Part ID {var_id} and name '{userd_var.name}' is missing in ensight variables."
            )
            continue

        try:
            # Normalize the strings before comparing names
            normalized_userd_name = normalize_string(userd_var.name)
            normalized_ensight_description = normalize_string(ensight_var.DESCRIPTION)
            assert (
                normalized_userd_name == normalized_ensight_description
            ), f"Variable names do not match for Part ID {var_id}: '{userd_var.name}' (userd) vs '{ensight_var.DESCRIPTION}' (ensight)"
        except AssertionError as e:
            failures.append(str(e))

        try:
            # Parse the type from pathname for comparison
            pyensight_type, pyensight_is_complex = get_var_type_and_complexity(
                ensight_var.VARTYPEENUM
            )
            assert (
                userd_var.type == pyensight_type
            ), f"Variable types do not match for Part ID {var_id} and name '{userd_var.name}': {userd_var.type} (userd) vs {pyensight_type} (ensight)"
        except AssertionError as e:
            failures.append(str(e))

        try:
            # Compare locations
            ensight_var_location = map_to_userd_variable_location(ensight_var.LOCATION).value
            assert (
                userd_var.location == ensight_var_location
            ), f"Variable locations do not match for Part ID {var_id} and name '{userd_var.name}': {userd_var.location} (userd) vs {ensight_var_location} (ensight)"
        except AssertionError as e:
            failures.append(str(e))

        try:
            # compare Is_complex
            assert (
                userd_var.isComplex == pyensight_is_complex
            ), f"Complexity do not match for Part ID {var_id} and name '{userd_var.name}': {userd_var.isComplex} (userd) vs {pyensight_is_complex} (ensight)"
        except AssertionError as e:
            failures.append(str(e))

    # Note: The following data typically does not align with most datasets due to metadata discrepancies.
    # TODO: Investigate and resolve metadata discrepancies to ensure data alignment across datasets.

    # try:
    #    # Compare metadata
    #    assert userd_var.metadata == ensight_var.metadata, \
    #        f"Variable metadata do not match for Part ID {var_id} and name '{userd_var.name}': {userd_var.metadata} (userd) vs {ensight_var.metadata} (ensight)"
    # except AssertionError as e:
    #    failures.append(str(e))

    # try:
    #    # Compare unit labels
    #    assert userd_var.unitLabel == ensight_var.ENS_UNITS_LABEL, \
    #        f"Unit labels do not match for Part ID {var_id} and name '{userd_var.name}': {userd_var.unitLabel} (userd) vs {ensight_var.ENS_UNITS_LABEL} (ensight)"
    # except AssertionError as e:
    #    failures.append(str(e))

    # try:
    #    # Compare unit dimensions
    #    assert userd_var.unitDims == ensight_var.ENS_UNITS_DIMS, \
    #        f"Unit dimensions do not match for Part ID {var_id} and name '{userd_var.name}': {userd_var.unitDims} (userd) vs {ensight_var.ENS_UNITS_DIMS} (ensight)"
    # except AssertionError as e:
    #    failures.append(str(e))

    # Return the list of failures and error code
    return failures, 0 if not failures else 1


def print_test_results(test_name, failures, error_code):
    if error_code == 0:
        print(f"{test_name}: PASS")
    else:
        print(f"{test_name}: FAIL")
        print("Failures:")
        for failure in failures:
            print(f" - {failure}")


def compare(userd, session, file1_userd, file2_userd, file1_session, file2_session, time_step):
    # Retrieve userd data
    (
        parts_userd,
        variables_userd,
        max_time_steps_userd,
        timestep_cache_userd,
        part_var_cache_userd,
    ) = get_all_userd_data(userd, file1_userd, file2_userd)

    # Retrieve pyEnSight data
    parts_pyensight, variables_pyensight = get_all_pyensight_data(
        session, file1_session, file2_session
    )

    # Test part lists
    part_failures, part_error_code = _test_parts(parts_userd, parts_pyensight)

    # Test variable lists
    variable_failures, variable_error_code = _test_variables(variables_userd, variables_pyensight)

    # Test variable values using the specified time_step
    variable_value_failures, variable_value_error_code = _test_variable_values(
        parts_userd,
        parts_pyensight,
        variables_userd,
        variables_pyensight,
        part_var_cache_userd,
        time_step,
    )

    # Print the test results for parts
    print_test_results("Part List Comparison", part_failures, part_error_code)

    # Print the test results for variables
    print_test_results("Variable List Comparison", variable_failures, variable_error_code)

    # Print the test results for variable values
    print_test_results(
        "Variable Values Comparison", variable_value_failures, variable_value_error_code
    )

    # Check for success or failure
    if part_error_code == 0 and variable_error_code == 0 and variable_value_error_code == 0:
        print("Overall Test: PASS\n")
    else:
        raise AssertionError(
            f"Overall Test: FAIL (part_error_code={part_error_code}, variable_error_code = {variable_error_code}, variable_value_error_code={variable_value_error_code})\n"
        )


def test_cfx(launch_libuserd_and_get_files):
    file_1 = "InjectMixer.res"
    file_2 = None
    rel_path = "result_files/cfx-mixing_elbow"

    # return file1_userd, file2_userd, file1_session, file2_session, libuserd, session, data_dir
    (
        file1_userd,
        file2_userd,
        file1_session,
        file2_session,
        userd,
        session,
        data_dir,
    ) = launch_libuserd_and_get_files(file_1, file_2, rel_path, rel_path)

    compare(userd, session, file1_userd, file2_userd, file1_session, file2_session, 0)


def test_fluent_hdf5(launch_libuserd_and_get_files):
    file_1 = "axial_comp-1-01438.cas.h5"
    file_2 = "axial_comp-1-01438.dat.h5"
    rel_path = "result_files/fluent-axial_comp"

    (
        file1_userd,
        file2_userd,
        file1_session,
        file2_session,
        userd,
        session,
        data_dir,
    ) = launch_libuserd_and_get_files(file_1, file_2, rel_path, rel_path)
    compare(userd, session, file1_userd, file2_userd, file1_session, file2_session, 0)
