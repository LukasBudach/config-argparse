import argparse
import datetime
import yaml

from pathlib import Path


class PersistentArgumentParser(argparse.ArgumentParser):
    def __init__(self, **kwargs):
        self._argument_required = {}
        self._parsed_args = None
        super(PersistentArgumentParser, self).__init__(**kwargs)
        self.add_argument('-c', '--config', type=str, help='Path to the configuration file to read.')

    def add_argument(self, *name_or_flags, **kwargs):
        require_arg = False
        if 'required' in kwargs:
            require_arg = kwargs['required']
            kwargs['required'] = False
        added_action = super(PersistentArgumentParser, self).add_argument(*name_or_flags, **kwargs)
        self._argument_required[added_action.dest] = require_arg

    def parse_args(self, **kwargs):
        self._parsed_args = super(PersistentArgumentParser, self).parse_args(**kwargs)

        update_config = True
        if self._parsed_args.config is not None:
            # convert path to config file to actual path
            self._parsed_args.config = Path(self._parsed_args.config)
            update_config = self._supplement_from_config(self._parsed_args.config)
        else:
            print('As there was no config file provided, the commandline arguments will be exported to a new one.')

        miss_required = self._validate_config()
        if miss_required:
            self.error('The configuration was invalid, the following required arguments were not set: {}'
                       .format(miss_required))

        if update_config or self._parsed_args.config is None:
            self._update_config_path_to_temporary()
            self._save_config()
        return self._parsed_args

    def parsed_args_to_dict(self):
        arg_dict = {}
        for arg in vars(self._parsed_args):
            if arg == 'config':
                arg_dict[arg] = str(getattr(self._parsed_args, arg))
            else:
                arg_dict[arg] = getattr(self._parsed_args, arg)
        return arg_dict

    def _update_config_path_to_temporary(self):
        now = datetime.datetime.now()
        target_path = Path('./configs/autosaved/config_{date}_{time}.yml'.format(date=now.strftime('%Y_%m_%d'),
                                                                                  time=now.strftime('%H_%M')))
        target_path.parent.mkdir(parents=True, exist_ok=True)
        self._parsed_args.config = target_path

    def _supplement_from_config(self, config: Path):
        conf_data = {}
        # load the config file
        with open(config, 'r') as cf:
            conf_data = yaml.load(cf)
        # convert saved config path to path object
        conf_data['config'] = Path(conf_data['config'])

        require_saving_updated_config = False
        if conf_data.keys() != vars(self._parsed_args).keys():
            print('The parsed arguments were not the same as the arguments provided in the config file. An updated '
                  'config will be written.')
            require_saving_updated_config = True

        # for each value in the config, set it in the Namespace if no value was set beforehand
        # remember whether all config values were used or not - if not, the config must be written again
        for arg in conf_data.keys():
            if arg not in vars(self._parsed_args):
                require_saving_updated_config = True
                continue
            cmd_line_val = getattr(self._parsed_args, arg)
            if cmd_line_val is None:
                setattr(self._parsed_args, arg, conf_data[arg])
            else:
                if conf_data[arg] != cmd_line_val:
                    print('The "{}" argument set in the command line overwrites the value set in the config file. An '
                          'updated config will be written.'.format(arg))
                    require_saving_updated_config = True
        return require_saving_updated_config

    def _validate_config(self):
        missing_args = []
        for arg_name in self._argument_required.keys():
            arg_required = self._argument_required[arg_name]
            if arg_required and (getattr(self._parsed_args, arg_name) is None):
                missing_args.append(arg_name)
        return missing_args

    def _save_config(self):
        with open(Path(self._parsed_args.config), 'w+') as cf:
            yaml.dump(self.parsed_args_to_dict(), cf)
            print('Saved the updated config file to {}'.format(self._parsed_args.config))


if __name__ == '__main__':
    parser = PersistentArgumentParser(description='Test parser.')

    parser.add_argument('-b', '--batch-size', required=True, type=int, help='Batch size to use for training.')
    parser.add_argument('-e', '--epochs', required=True, type=int, help='Number of epochs to train for.')
    parser.add_argument('--num-gpus', required=True, type=int, help='Number of GPUs available to be used during training.')
    parser.add_argument('--train-data', required=True, type=str, help='Path to or autogluon handler for train dataset.')
    parser.add_argument('--val-data', required=False, type=str, help='Path to or autogluon handler for validation dataset.')

    args = parser.parse_args()
