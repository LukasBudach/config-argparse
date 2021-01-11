import argparse
import datetime
import yaml

from pathlib import Path


class _PersistentMutuallyExclusiveGroup(argparse._MutuallyExclusiveGroup):
    def __init__(self, container, required=False):
        super(_PersistentMutuallyExclusiveGroup, self).__init__(container, required=required)

    def _add_action(self, action):
        action = super(_PersistentMutuallyExclusiveGroup, self)._add_action(action)
        self._container._register_mutex_group_action(self, action)
        return action


class PersistentArgumentParser(argparse.ArgumentParser):
    def __init__(self, **kwargs):
        self._arg_dest_object_map = {}
        self._argument_required = {}
        self._mutex_required_dict = {}
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
        self._arg_dest_object_map[added_action.dest] = added_action

    def add_mutually_exclusive_group(self, **kwargs):
        require_group = False
        if 'required' in kwargs:
            require_group = kwargs['required']
            kwargs['required'] = False

        group = _PersistentMutuallyExclusiveGroup(self, **kwargs)
        self._mutually_exclusive_groups.append(group)
        self._mutex_required_dict[len(self._mutually_exclusive_groups) - 1] = [require_group]
        return group

    def _register_mutex_group_action(self, group, action):
        g_id = self._mutually_exclusive_groups.index(group)
        self._mutex_required_dict[g_id].append(action.dest)
        self._argument_required[action.dest] = g_id

    def _parse_known_args(self, arg_strings, namespace):
        self._parsed_args, args = super(PersistentArgumentParser, self)._parse_known_args(arg_strings, namespace)

        update_config = True
        if self._parsed_args.config is not None:
            # convert path to config file to actual path
            self._parsed_args.config = Path(self._parsed_args.config)
            update_config = self._supplement_from_config(self._parsed_args.config)
        else:
            print('As there was no config file provided, the command line arguments will be exported to a new one if '
                  'they are valid.')

        self._validate_config()

        if update_config or self._parsed_args.config is None:
            self._update_config_path_to_temporary()
            self._save_config()

        return self._parsed_args, args

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
            conf_data = yaml.load(cf, Loader=yaml.FullLoader)
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
            elif isinstance(self._arg_dest_object_map[arg], argparse._StoreConstAction) \
                    and (cmd_line_val != self._arg_dest_object_map[arg].const):
                print('Ping')
                setattr(self._parsed_args, arg, conf_data[arg])
            else:
                if conf_data[arg] != cmd_line_val:
                    print('The "{}" argument set in the command line overwrites the value set in the config file. An '
                          'updated config will be written.'.format(arg))
                    require_saving_updated_config = True
        return require_saving_updated_config

    def _validate_config(self):
        error_msg = ''
        missing_args = []
        handled_mutex_groups = []
        for arg_name in self._argument_required.keys():
            arg_required = self._argument_required[arg_name]
            if type(arg_required) is int:
                if arg_required not in handled_mutex_groups:
                    error_msg += self._validate_mutex_group(arg_required)
                    handled_mutex_groups.append(arg_required)
                continue
            missing_args.extend(self._validate_argument(arg_name, arg_required))

        if missing_args:
            error_msg += '\nThe configuration was invalid, the following required arguments were not set: {}'\
                .format(missing_args)

        if error_msg != '':
            self.error(error_msg)

    def _validate_argument(self, arg_name, is_required):
        if is_required and (getattr(self._parsed_args, arg_name) is None):
            return [arg_name]
        return []

    def _validate_mutex_group(self, g_id):
        is_required = self._mutex_required_dict[g_id][0]
        if not is_required:
            return ''
        arg_names = self._mutex_required_dict[g_id][1:]
        any_set = False
        fields_set = []
        for arg_name in arg_names:
            if getattr(self._parsed_args, arg_name) is not None:
                any_set = True
                fields_set.append(arg_name)
        if not any_set:
            return '\nOne of the following fields must be set: {}'.format(', '.join(arg_names))
        elif len(fields_set) > 1:
            return '\nThe following fields are not allowed to be set together: {}'.format(', '.join(fields_set))
        return ''

    def _save_config(self):
        with open(Path(self._parsed_args.config), 'w+') as cf:
            yaml.dump(self.parsed_args_to_dict(), cf)
            print('Saved the updated config file to {}'.format(self._parsed_args.config))
