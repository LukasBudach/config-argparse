from src.PersistentArgumentParser import PersistentArgumentParser

import argparse
import pathlib
import shutil
import unittest


class TestPersistentArgumentParser(unittest.TestCase):
    def setUp(self):
        self.parser = PersistentArgumentParser()

        self.arg_input = []
        self.ref_result = argparse.Namespace()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(pathlib.Path.cwd() / 'configs', ignore_errors=True)

    def _construct_parser(self, test_args):
        mutex_groups = {}
        for arg_name in test_args:
            if test_args[arg_name][1] is None:
                self.parser.add_argument('--' + arg_name, required=test_args[arg_name][0])
            elif test_args[arg_name][1] in mutex_groups.keys():
                mutex_groups[test_args[arg_name][1]].add_argument('--' + arg_name)
            else:
                mutex_groups[test_args[arg_name][1]] = self.parser.add_mutually_exclusive_group(required=test_args[arg_name][0])
                mutex_groups[test_args[arg_name][1]].add_argument('--' + arg_name)

    def _construct_arg_input_and_ref_results(self, test_args):
        for arg_name in test_args:
            if test_args[arg_name][2] is not None:
                self.arg_input.append('--' + arg_name)
                self.arg_input.append(test_args[arg_name][2])
            # add argument to reference namespace
            setattr(self.ref_result, arg_name.replace('-', '_'), test_args[arg_name][2])

    def _validate_parser_result(self, test_args):
        self._construct_arg_input_and_ref_results(test_args)
        res = self.parser.parse_args(args=self.arg_input)
        # make sure that a config file is defined and remove afterwards
        self.assertIsNotNone(res.config)
        delattr(res, 'config')

        self.assertEqual(self.ref_result, res)

    def testParseNonRequiredArgs(self):
        # maps argument name to list [required, Part of MutExGroup (ID if applicable), value to be set)
        test_args = {
            'test-arg-one': [False, None, None],
            'test-arg-two': [False, None, None],
            'test-arg-three': [False, None, 'val']
        }

        self._construct_parser(test_args)
        self._validate_parser_result(test_args)

    def testParseRequiredArgs(self):
        # maps argument name to list [required, Part of MutExGroup (ID if applicable), value to be set)
        test_args = {
            'test-arg-one': [True, None, 'some'],
            'test-arg-two': [False, None, None],
            'test-arg-three': [True, None, 'val']
        }

        self._construct_parser(test_args)
        self._validate_parser_result(test_args)

    def testParseRequiredArgsMissing(self):
        test_args = {
            'test-arg-one': [True, None, None],
            'test-arg-two': [False, None, None],
            'test-arg-three': [True, None, 'val']
        }
        self._construct_parser(test_args)
        self._construct_arg_input_and_ref_results(test_args)
        with self.assertRaises(SystemExit) as e:
            self.parser.parse_args(args=self.arg_input)
        self.assertEqual(2, e.exception.code)

    def testParseNonRequiredMutexGroup(self):
        test_args = {
            'test-arg-one': [False, 0, 'some'],
            'test-arg-two': [False, 1, None],
            'test-arg-three': [False, None, 'val'],
            'test-arg-four': [False, 1, None],
            'test-arg-five': [False, 0, None]
        }

        self._construct_parser(test_args)
        self._validate_parser_result(test_args)

    def testParseRequiredMutexGroup(self):
        test_args = {
            'test-arg-one': [True, 0, None],
            'test-arg-two': [True, 1, 'val'],
            'test-arg-three': [True, 1, None],
            'test-arg-four': [True, 0, 'some']
        }

        self._construct_parser(test_args)
        self._validate_parser_result(test_args)

    def testParseRequiredMutexGroupMissing(self):
        test_args = {
            'test-arg-one': [True, 0, None],
            'test-arg-two': [True, 0, None]
        }

        self._construct_parser(test_args)
        self._construct_arg_input_and_ref_results(test_args)
        with self.assertRaises(SystemExit) as e:
            self.parser.parse_args(args=self.arg_input)
        self.assertEqual(2, e.exception.code)

    def testParseMutexGroupBothSet(self):
        test_args = {
            'test-arg-one': [True, 0, 'some'],
            'test-arg-two': [True, 0, 'val']
        }

        self._construct_parser(test_args)
        self._construct_arg_input_and_ref_results(test_args)
        with self.assertRaises(SystemExit) as e:
            self.parser.parse_args(args=self.arg_input)
        self.assertEqual(2, e.exception.code)


if __name__ == '__main__':
    unittest.main()
