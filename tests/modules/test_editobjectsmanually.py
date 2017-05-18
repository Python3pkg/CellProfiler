'''test_editobjectsmanually - test the EditObjectsManually module
'''

import base64
import unittest
import zlib
from io import StringIO

import cellprofiler.measurement
import numpy as np

from cellprofiler.preferences import set_headless

set_headless()

import cellprofiler.workspace as cpw
import cellprofiler.pipeline as cpp
import cellprofiler.object as cpo
import cellprofiler.image as cpi
import cellprofiler.measurement as cpmeas
import cellprofiler.modules.editobjectsmanually as E

INPUT_OBJECTS_NAME = "inputobjects"
OUTPUT_OBJECTS_NAME = "outputobjects"


class TestEditObjectsManually(unittest.TestCase):
    def test_01_02_load_v1(self):
        data = r"""CellProfiler Pipeline: http://www.cellprofiler.org
Version:1
SVNRevision:9120

EditObjectsManually:[module_num:1|svn_version:\'1\'|variable_revision_number:1|show_window:True|notes:\x5B\x5D]
    Select the input objects:Nuclei
    Name the objects left after editing:EditedNuclei
    Do you want to save outlines of the edited objects?:Yes
    What do you want to call the outlines?:EditedNucleiOutlines
    Do you want to renumber the objects created by this module or retain the original numbering?:Renumber
"""
        pipeline = cpp.Pipeline()

        def callback(caller, event):
            self.assertFalse(isinstance(event, cpp.LoadExceptionEvent))

        pipeline.add_listener(callback)
        pipeline.load(StringIO(data))
        self.assertEqual(len(pipeline.modules()), 1)
        module = pipeline.modules()[0]
        self.assertTrue(isinstance(module, E.EditObjectsManually))
        self.assertEqual(module.object_name, "Nuclei")
        self.assertEqual(module.filtered_objects, "EditedNuclei")
        self.assertTrue(module.wants_outlines)
        self.assertEqual(module.outlines_name, "EditedNucleiOutlines")
        self.assertEqual(module.renumber_choice, E.R_RENUMBER)
        self.assertFalse(module.wants_image_display)

    def test_01_03_load_v2(self):
        data = r"""CellProfiler Pipeline: http://www.cellprofiler.org
Version:1
SVNRevision:9120

EditObjectsManually:[module_num:1|svn_version:\'10039\'|variable_revision_number:2|show_window:True|notes:\x5B\x5D]
    Select the objects to be edited:Nuclei
    Name the edited objects:EditedNuclei
    Retain outlines of the edited objects?:No
    Name the outline image:EditedObjectOutlines
    Numbering of the edited objects:Retain
    Display a guiding image?:Yes
    Image name\x3A:DNA
"""
        pipeline = cpp.Pipeline()

        def callback(caller, event):
            self.assertFalse(isinstance(event, cpp.LoadExceptionEvent))

        pipeline.add_listener(callback)
        pipeline.load(StringIO(data))
        self.assertEqual(len(pipeline.modules()), 1)
        module = pipeline.modules()[0]
        self.assertTrue(isinstance(module, E.EditObjectsManually))
        self.assertEqual(module.object_name, "Nuclei")
        self.assertEqual(module.filtered_objects, "EditedNuclei")
        self.assertFalse(module.wants_outlines)
        self.assertEqual(module.renumber_choice, E.R_RETAIN)
        self.assertTrue(module.wants_image_display)
        self.assertEqual(module.image_name, "DNA")
        self.assertFalse(module.allow_overlap)

    def test_01_04_load_v3(self):
        data = r"""CellProfiler Pipeline: http://www.cellprofiler.org
Version:1
SVNRevision:9120

EditObjectsManually:[module_num:1|svn_version:\'10039\'|variable_revision_number:3|show_window:True|notes:\x5B\x5D]
    Select the objects to be edited:Nuclei
    Name the edited objects:EditedNuclei
    Retain outlines of the edited objects?:No
    Name the outline image:EditedObjectOutlines
    Numbering of the edited objects:Retain
    Display a guiding image?:Yes
    Image name\x3A:DNA
    Allow overlapping objects:Yes
"""
        pipeline = cpp.Pipeline()

        def callback(caller, event):
            self.assertFalse(isinstance(event, cpp.LoadExceptionEvent))

        pipeline.add_listener(callback)
        pipeline.load(StringIO(data))
        self.assertEqual(len(pipeline.modules()), 1)
        module = pipeline.modules()[0]
        self.assertTrue(isinstance(module, E.EditObjectsManually))
        self.assertEqual(module.object_name, "Nuclei")
        self.assertEqual(module.filtered_objects, "EditedNuclei")
        self.assertFalse(module.wants_outlines)
        self.assertEqual(module.renumber_choice, E.R_RETAIN)
        self.assertTrue(module.wants_image_display)
        self.assertEqual(module.image_name, "DNA")
        self.assertTrue(module.allow_overlap)

    def test_02_02_measurements(self):
        module = E.EditObjectsManually()
        module.object_name.value = INPUT_OBJECTS_NAME
        module.filtered_objects.value = OUTPUT_OBJECTS_NAME

        columns = module.get_measurement_columns(None)
        expected_columns = [
            (cpmeas.IMAGE, cellprofiler.measurement.FF_COUNT % OUTPUT_OBJECTS_NAME, cpmeas.COLTYPE_INTEGER),
            (OUTPUT_OBJECTS_NAME, cellprofiler.measurement.M_NUMBER_OBJECT_NUMBER, cpmeas.COLTYPE_INTEGER),
            (OUTPUT_OBJECTS_NAME, cellprofiler.measurement.M_LOCATION_CENTER_X, cpmeas.COLTYPE_FLOAT),
            (OUTPUT_OBJECTS_NAME, cellprofiler.measurement.M_LOCATION_CENTER_Y, cpmeas.COLTYPE_FLOAT),
            (OUTPUT_OBJECTS_NAME, cellprofiler.measurement.FF_PARENT % INPUT_OBJECTS_NAME, cpmeas.COLTYPE_INTEGER),
            (INPUT_OBJECTS_NAME, cellprofiler.measurement.FF_CHILDREN_COUNT % OUTPUT_OBJECTS_NAME, cpmeas.COLTYPE_INTEGER)]

        for column in columns:
            self.assertTrue(any([all([column[i] == expected[i] for i in range(3)])
                                 for expected in expected_columns]),
                            "Unexpected column: %s, %s, %s" % column)
            # Make sure no duplicates
            self.assertEqual(len(['x' for c in columns
                                  if all([column[i] == c[i]
                                          for i in range(3)])]), 1)
        for expected in expected_columns:
            self.assertTrue(any([all([column[i] == expected[i] for i in range(3)])
                                 for column in columns]),
                            "Missing column: %s, %s, %s" % expected)

        #
        # Check the measurement features
        #
        d = {cpmeas.IMAGE: {cellprofiler.measurement.C_COUNT: [OUTPUT_OBJECTS_NAME],
                            "Foo": []},
             INPUT_OBJECTS_NAME: {cellprofiler.measurement.C_CHILDREN: ["%s_Count" % OUTPUT_OBJECTS_NAME],
                                  "Foo": []},
             OUTPUT_OBJECTS_NAME: {
                 cellprofiler.measurement.C_LOCATION: [cellprofiler.measurement.FTR_CENTER_X,
                                                       cellprofiler.measurement.FTR_CENTER_Y],
                 cellprofiler.measurement.C_PARENT: [INPUT_OBJECTS_NAME],
                 cellprofiler.measurement.C_NUMBER: [cellprofiler.measurement.FTR_OBJECT_NUMBER],
                 "Foo": []},
             "Foo": {}
             }

        for object_name, category_d in d.items():
            #
            # Check get_categories for the object
            #
            categories = module.get_categories(None, object_name)
            self.assertEqual(len(categories), len([k for k in list(category_d.keys())
                                                   if k != "Foo"]))
            for category in categories:
                self.assertTrue(category in category_d)
            for category in list(category_d.keys()):
                if category != "Foo":
                    self.assertTrue(category in categories)

            for category, expected_features in category_d.items():
                #
                # check get_measurements for each category
                #
                features = module.get_measurements(None, object_name,
                                                   category)
                self.assertEqual(len(features), len(expected_features))
                for feature in features:
                    self.assertTrue(feature in expected_features,
                                    "Unexpected feature: %s" % feature)
                for feature in expected_features:
                    self.assertTrue(feature in features,
                                    "Missing feature: %s" % feature)
