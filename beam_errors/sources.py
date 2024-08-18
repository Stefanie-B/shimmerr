import numpy as np


class Source:
    def __init__(
        self,
        right_ascension,
        declination,
        brightness,
        reference_frequency,
        spectral_index,
        logSI,
    ):
        self.ra = self.parse_right_ascension(right_ascension)
        self.dec = self.parse_declination(declination)
        if logSI:
            self.I = lambda v: self.logarithmic_spectral_index_brightness(
                v, brightness, reference_frequency, spectral_index
            )
        else:
            self.I = lambda v: self.linear_spectral_index_brightness(
                v, brightness, reference_frequency, spectral_index
            )

    @staticmethod
    def parse_right_ascension(right_ascension_string):
        right_ascension_string = right_ascension_string.strip(" ")
        HA, min, sec = right_ascension_string.split(":")

        # Check for negative angles
        sign = -1 if HA[0] == "-" else 1

        # 1 hour 15 degrees (15*24=360)
        right_ascension_degrees = abs(int(HA)) * 15 + int(min) / 4 + float(sec) / 240
        return sign * right_ascension_degrees

    @staticmethod
    def parse_declination(declination_string):
        declination_string = declination_string.replace(" ", "")
        declination_string = declination_string.strip("+")
        fields = declination_string.split(".")
        deg = int(fields[0])
        min = int(fields[1])
        sec = float(".".join(fields[2:]))  # Accepts either an integer or a float
        declination_degrees = abs(deg) + min / 60 + sec / 3600
        return np.sign(deg) * declination_degrees

    @staticmethod
    def logarithmic_spectral_index_brightness(
        frequency, brightness, reference_frequency, spectral_index
    ):
        spectral_index = spectral_index.strip("[]").split(",")
        x = frequency / reference_frequency
        spectral_shape = x ** (
            sum(float(c) * np.log10(x) ** i for i, c in enumerate(spectral_index))
        )
        return brightness * spectral_shape

    @staticmethod
    def linear_spectral_index_brightness(
        frequency, brightness, reference_frequency, spectral_index
    ):
        spectral_index = spectral_index.strip("[]").split(",")
        x = frequency / reference_frequency - 1
        spectral_shape = sum(float(c) * x**i for i, c in enumerate(spectral_index))
        return brightness + spectral_shape


class Patch:
    def __init__(
        self,
        patch_right_ascension,
        patch_declination,
    ):
        self.elements = {}
        self.ra = Source.parse_right_ascension(patch_right_ascension)
        self.dec = Source.parse_declination(patch_declination)

    def add_source(
        self,
        source_name,
        right_ascension,
        declination,
        brightness,
        reference_frequency,
        spectral_index,
        logSI,
    ):
        self.elements[source_name] = Source(
            right_ascension=right_ascension,
            declination=declination,
            brightness=brightness,
            reference_frequency=reference_frequency,
            spectral_index=spectral_index,
            logSI=logSI,
        )


class Skymodel:
    def __init__(self, filename):

        self.elements = {}
        with open(filename, "r") as f:
            self.parse_formatstring(f.readline())
            for inputline in f:
                inputline = inputline.rstrip("\n")

                # Skip comments
                if inputline.startswith("#") or inputline.replace(",", "") == "":
                    continue
                inputfields = inputline.split(",")

                # For readability
                def get_item(itemname):
                    try:
                        return inputfields[self.items[itemname]].strip(" ")
                    except IndexError:
                        return ""

                # New patch
                patch_name = get_item("patch")
                if patch_name not in self.elements.keys():
                    # Check if this is actually a patch definition or a sneaky source
                    if get_item("i") != "":
                        raise ValueError(
                            f"Patch {patch_name} has not been defined before adding sources."
                        )
                    # Add a new patch
                    self.elements[patch_name] = Patch(
                        patch_right_ascension=get_item("ra"),
                        patch_declination=get_item("dec"),
                    )

                else:
                    # Check if a reference frequency has been given or if we use the default
                    try:
                        reference_frequency = float(get_item("referencefrequency"))
                    except ValueError:
                        reference_frequency = get_item("default_referencefrequency")

                    # Fill in whether the spectral index is logarithmic
                    try:
                        logSI = (
                            get_item("logarithmicsi") == "true"
                        )  # can't cast to bool, that just checks whether the string is empty
                    except KeyError:
                        logSI = True

                    # Add the source
                    self.elements[patch_name].add_source(
                        source_name=get_item("name"),
                        right_ascension=get_item("ra"),
                        declination=get_item("dec"),
                        brightness=float(get_item("i")),
                        reference_frequency=reference_frequency,
                        spectral_index=get_item("spectralindex"),
                        logSI=logSI,
                    )

    def parse_formatstring(self, string):
        # Anything not in this list will be ignored
        list_of_itemnames = [
            "name",
            "patch",
            "ra",
            "dec",
            "i",
            "referencefrequency",
            "spectralindex",
            "logarithmicsi",
        ]

        # remove capitalization, spaces and 'format=' and split the string into fields
        string = string.lower()
        string = string.replace(" ", "")
        fields = string.split(",")

        # Create a dictionary with the indexes of the fields
        self.items = {}
        for itemname in list_of_itemnames:
            # If a value is not in the file, we skip it
            try:
                matching_string = list(filter(lambda x: itemname in x, fields))[0]
            except IndexError:
                if itemname == "spectralindex" or itemname == "logarithmicsi":
                    continue
                raise KeyError(f"Item {itemname} missing from sky model")
            self.items[itemname] = fields.index(matching_string)

            # There is a default value for the reference frequency that we also need to save
            if itemname == "referencefrequency":
                _, default_reference_frequency = matching_string.split("=")
                default_reference_frequency = "".join(
                    i
                    for i in default_reference_frequency
                    if i.isdigit()
                    or i == "e"
                    or i == "-"  # e and - are needed for numbers like 5e-1
                )
                self.items["default_referencefrequency"] = float(
                    default_reference_frequency
                )
