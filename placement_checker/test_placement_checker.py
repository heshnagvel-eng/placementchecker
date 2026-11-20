import unittest
from placement_checker import validate_reply, student_qualifies, REQUIRED_FIELDS

class PlacementCheckerTests(unittest.TestCase):
    def test_valid_post_extraction(self):
        post = "CSE branch, CGPA 7.0, maximum 1 backlog, batch 2027."
        raw = {"branches":["CSE"],"min_cgpa":7.0,"max_backlogs":1,"batch":2027,"summary":"CSE graduate role"}
        result = validate_reply(raw, post)
        self.assertEqual(result["branches"], ["CSE"])
        self.assertEqual(result["min_cgpa"], 7.0)

    def test_percentage_not_converted(self):
        post = "CSE branch with 75 percent marks."
        raw = {"branches":["CSE"],"min_cgpa":7.5,"max_backlogs":None,"batch":None,"summary":"Percentage requirement"}
        result = validate_reply(raw, post)
        self.assertIsNone(result["min_cgpa"])

    def test_unmentioned_branch_removed(self):
        post = "CSE branch, CGPA 7.0."
        raw = {"branches":["CSE","IT"],"min_cgpa":7.0,"max_backlogs":None,"batch":None,"summary":"Branch requirement"}
        result = validate_reply(raw, post)
        self.assertEqual(result["branches"], ["CSE"])

    def test_all_requires_explicit_phrase(self):
        post = "CSE and IT branches, CGPA 6.0."
        raw = {"branches":["ALL"],"min_cgpa":6.0,"max_backlogs":None,"batch":None,"summary":"All branches"}
        result = validate_reply(raw, post)
        self.assertEqual(result["branches"], [])

    def test_no_backlogs_means_zero(self):
        post = "Any branch, CGPA 6.5, no backlogs."
        raw = {"branches":["ALL"],"min_cgpa":6.5,"max_backlogs":0,"batch":None,"summary":"Any branch role"}
        result = validate_reply(raw, post)
        self.assertEqual(result["max_backlogs"], 0)

    def test_eligibility(self):
        criteria = {"branches":["CSE"],"min_cgpa":7.0,"max_backlogs":1,"batch":2027,"summary":"test"}
        student = {"branch":"CSE","cgpa":"7.5","backlogs":"1","batch":"2027"}
        self.assertTrue(student_qualifies(student, criteria))

    def test_ineligible_due_to_backlogs(self):
        criteria = {"branches":["CSE"],"min_cgpa":7.0,"max_backlogs":1,"batch":2027,"summary":"test"}
        student = {"branch":"CSE","cgpa":"8.5","backlogs":"2","batch":"2027"}
        self.assertFalse(student_qualifies(student, criteria))

if __name__ == "__main__":
    unittest.main(verbosity=2)
