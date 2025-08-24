📂 Estructura (v0.4.0)
etl-mini/
│   .gitattributes
│   .gitignore
│   CHANGELOG.md
│   GENERAL_DESC_CODES.md
│   LICENSE
│   NOTICE
│   python
│   README.md
│   requirements.txt
│   run_etl.bat
│   run_etl.sh
│   serve.cmd
│
├───.github
│   └───workflows
│           ci.yml
│
├───.venv
│   │   pyvenv.cfg
│   │
│   ├───Include
│   ├───Lib
│   │   └───site-packages
│   │       ├───pip
│   │       │   │   py.typed
│   │       │   │   __init__.py
│   │       │   │   __main__.py
│   │       │   │   __pip-runner__.py
│   │       │   │
│   │       │   ├───_internal
│   │       │   │   │   build_env.py
│   │       │   │   │   cache.py
│   │       │   │   │   configuration.py
│   │       │   │   │   exceptions.py
│   │       │   │   │   main.py
│   │       │   │   │   pyproject.py
│   │       │   │   │   self_outdated_check.py
│   │       │   │   │   wheel_builder.py
│   │       │   │   │   __init__.py
│   │       │   │   │
│   │       │   │   ├───cli
│   │       │   │   │   │   autocompletion.py
│   │       │   │   │   │   base_command.py
│   │       │   │   │   │   cmdoptions.py
│   │       │   │   │   │   command_context.py
│   │       │   │   │   │   main.py
│   │       │   │   │   │   main_parser.py
│   │       │   │   │   │   parser.py
│   │       │   │   │   │   progress_bars.py
│   │       │   │   │   │   req_command.py
│   │       │   │   │   │   spinners.py
│   │       │   │   │   │   status_codes.py
│   │       │   │   │   │   __init__.py
│   │       │   │   │   │
│   │       │   │   │   └───__pycache__
│   │       │   │   │           autocompletion.cpython-312.pyc
│   │       │   │   │           base_command.cpython-312.pyc
│   │       │   │   │           cmdoptions.cpython-312.pyc
│   │       │   │   │           command_context.cpython-312.pyc
│   │       │   │   │           main.cpython-312.pyc
│   │       │   │   │           main_parser.cpython-312.pyc
│   │       │   │   │           parser.cpython-312.pyc
│   │       │   │   │           progress_bars.cpython-312.pyc
│   │       │   │   │           req_command.cpython-312.pyc
│   │       │   │   │           spinners.cpython-312.pyc
│   │       │   │   │           status_codes.cpython-312.pyc
│   │       │   │   │           __init__.cpython-312.pyc
│   │       │   │   │
│   │       │   │   ├───commands
│   │       │   │   │   │   cache.py
│   │       │   │   │   │   check.py
│   │       │   │   │   │   completion.py
│   │       │   │   │   │   configuration.py
│   │       │   │   │   │   debug.py
│   │       │   │   │   │   download.py
│   │       │   │   │   │   freeze.py
│   │       │   │   │   │   hash.py
│   │       │   │   │   │   help.py
│   │       │   │   │   │   index.py
│   │       │   │   │   │   inspect.py
│   │       │   │   │   │   install.py
│   │       │   │   │   │   list.py
│   │       │   │   │   │   search.py
│   │       │   │   │   │   show.py
│   │       │   │   │   │   uninstall.py
│   │       │   │   │   │   wheel.py
│   │       │   │   │   │   __init__.py
│   │       │   │   │   │
│   │       │   │   │   └───__pycache__
│   │       │   │   │           cache.cpython-312.pyc
│   │       │   │   │           check.cpython-312.pyc
│   │       │   │   │           completion.cpython-312.pyc
│   │       │   │   │           configuration.cpython-312.pyc
│   │       │   │   │           debug.cpython-312.pyc
│   │       │   │   │           download.cpython-312.pyc
│   │       │   │   │           freeze.cpython-312.pyc
│   │       │   │   │           hash.cpython-312.pyc
│   │       │   │   │           help.cpython-312.pyc
│   │       │   │   │           index.cpython-312.pyc
│   │       │   │   │           inspect.cpython-312.pyc
│   │       │   │   │           install.cpython-312.pyc
│   │       │   │   │           list.cpython-312.pyc
│   │       │   │   │           search.cpython-312.pyc
│   │       │   │   │           show.cpython-312.pyc
│   │       │   │   │           uninstall.cpython-312.pyc
│   │       │   │   │           wheel.cpython-312.pyc
│   │       │   │   │           __init__.cpython-312.pyc
│   │       │   │   │
│   │       │   │   ├───distributions
│   │       │   │   │   │   base.py
│   │       │   │   │   │   installed.py
│   │       │   │   │   │   sdist.py
│   │       │   │   │   │   wheel.py
│   │       │   │   │   │   __init__.py
│   │       │   │   │   │
│   │       │   │   │   └───__pycache__
│   │       │   │   │           base.cpython-312.pyc
│   │       │   │   │           installed.cpython-312.pyc
│   │       │   │   │           sdist.cpython-312.pyc
│   │       │   │   │           wheel.cpython-312.pyc
│   │       │   │   │           __init__.cpython-312.pyc
│   │       │   │   │
│   │       │   │   ├───index
│   │       │   │   │   │   collector.py
│   │       │   │   │   │   package_finder.py
│   │       │   │   │   │   sources.py
│   │       │   │   │   │   __init__.py
│   │       │   │   │   │
│   │       │   │   │   └───__pycache__
│   │       │   │   │           collector.cpython-312.pyc
│   │       │   │   │           package_finder.cpython-312.pyc
│   │       │   │   │           sources.cpython-312.pyc
│   │       │   │   │           __init__.cpython-312.pyc
│   │       │   │   │
│   │       │   │   ├───locations
│   │       │   │   │   │   base.py
│   │       │   │   │   │   _distutils.py
│   │       │   │   │   │   _sysconfig.py
│   │       │   │   │   │   __init__.py
│   │       │   │   │   │
│   │       │   │   │   └───__pycache__
│   │       │   │   │           base.cpython-312.pyc
│   │       │   │   │           _distutils.cpython-312.pyc
│   │       │   │   │           _sysconfig.cpython-312.pyc
│   │       │   │   │           __init__.cpython-312.pyc
│   │       │   │   │
│   │       │   │   ├───metadata
│   │       │   │   │   │   base.py
│   │       │   │   │   │   pkg_resources.py
│   │       │   │   │   │   _json.py
│   │       │   │   │   │   __init__.py
│   │       │   │   │   │
│   │       │   │   │   ├───importlib
│   │       │   │   │   │   │   _compat.py
│   │       │   │   │   │   │   _dists.py
│   │       │   │   │   │   │   _envs.py
│   │       │   │   │   │   │   __init__.py
│   │       │   │   │   │   │
│   │       │   │   │   │   └───__pycache__
│   │       │   │   │   │           _compat.cpython-312.pyc
│   │       │   │   │   │           _dists.cpython-312.pyc
│   │       │   │   │   │           _envs.cpython-312.pyc
│   │       │   │   │   │           __init__.cpython-312.pyc
│   │       │   │   │   │
│   │       │   │   │   └───__pycache__
│   │       │   │   │           base.cpython-312.pyc
│   │       │   │   │           pkg_resources.cpython-312.pyc
│   │       │   │   │           _json.cpython-312.pyc
│   │       │   │   │           __init__.cpython-312.pyc
│   │       │   │   │
│   │       │   │   ├───models
│   │       │   │   │   │   candidate.py
│   │       │   │   │   │   direct_url.py
│   │       │   │   │   │   format_control.py
│   │       │   │   │   │   index.py
│   │       │   │   │   │   installation_report.py
│   │       │   │   │   │   link.py
│   │       │   │   │   │   scheme.py
│   │       │   │   │   │   search_scope.py
│   │       │   │   │   │   selection_prefs.py
│   │       │   │   │   │   target_python.py
│   │       │   │   │   │   wheel.py
│   │       │   │   │   │   __init__.py
│   │       │   │   │   │
│   │       │   │   │   └───__pycache__
│   │       │   │   │           candidate.cpython-312.pyc
│   │       │   │   │           direct_url.cpython-312.pyc
│   │       │   │   │           format_control.cpython-312.pyc
│   │       │   │   │           index.cpython-312.pyc
│   │       │   │   │           installation_report.cpython-312.pyc
│   │       │   │   │           link.cpython-312.pyc
│   │       │   │   │           scheme.cpython-312.pyc
│   │       │   │   │           search_scope.cpython-312.pyc
│   │       │   │   │           selection_prefs.cpython-312.pyc
│   │       │   │   │           target_python.cpython-312.pyc
│   │       │   │   │           wheel.cpython-312.pyc
│   │       │   │   │           __init__.cpython-312.pyc
│   │       │   │   │
│   │       │   │   ├───network
│   │       │   │   │   │   auth.py
│   │       │   │   │   │   cache.py
│   │       │   │   │   │   download.py
│   │       │   │   │   │   lazy_wheel.py
│   │       │   │   │   │   session.py
│   │       │   │   │   │   utils.py
│   │       │   │   │   │   xmlrpc.py
│   │       │   │   │   │   __init__.py
│   │       │   │   │   │
│   │       │   │   │   └───__pycache__
│   │       │   │   │           auth.cpython-312.pyc
│   │       │   │   │           cache.cpython-312.pyc
│   │       │   │   │           download.cpython-312.pyc
│   │       │   │   │           lazy_wheel.cpython-312.pyc
│   │       │   │   │           session.cpython-312.pyc
│   │       │   │   │           utils.cpython-312.pyc
│   │       │   │   │           xmlrpc.cpython-312.pyc
│   │       │   │   │           __init__.cpython-312.pyc
│   │       │   │   │
│   │       │   │   ├───operations
│   │       │   │   │   │   check.py
│   │       │   │   │   │   freeze.py
│   │       │   │   │   │   prepare.py
│   │       │   │   │   │   __init__.py
│   │       │   │   │   │
│   │       │   │   │   ├───build
│   │       │   │   │   │   │   build_tracker.py
│   │       │   │   │   │   │   metadata.py
│   │       │   │   │   │   │   metadata_editable.py
│   │       │   │   │   │   │   metadata_legacy.py
│   │       │   │   │   │   │   wheel.py
│   │       │   │   │   │   │   wheel_editable.py
│   │       │   │   │   │   │   wheel_legacy.py
│   │       │   │   │   │   │   __init__.py
│   │       │   │   │   │   │
│   │       │   │   │   │   └───__pycache__
│   │       │   │   │   │           build_tracker.cpython-312.pyc
│   │       │   │   │   │           metadata.cpython-312.pyc
│   │       │   │   │   │           metadata_editable.cpython-312.pyc
│   │       │   │   │   │           metadata_legacy.cpython-312.pyc
│   │       │   │   │   │           wheel.cpython-312.pyc
│   │       │   │   │   │           wheel_editable.cpython-312.pyc
│   │       │   │   │   │           wheel_legacy.cpython-312.pyc
│   │       │   │   │   │           __init__.cpython-312.pyc
│   │       │   │   │   │
│   │       │   │   │   ├───install
│   │       │   │   │   │   │   editable_legacy.py
│   │       │   │   │   │   │   wheel.py
│   │       │   │   │   │   │   __init__.py
│   │       │   │   │   │   │
│   │       │   │   │   │   └───__pycache__
│   │       │   │   │   │           editable_legacy.cpython-312.pyc
│   │       │   │   │   │           wheel.cpython-312.pyc
│   │       │   │   │   │           __init__.cpython-312.pyc
│   │       │   │   │   │
│   │       │   │   │   └───__pycache__
│   │       │   │   │           check.cpython-312.pyc
│   │       │   │   │           freeze.cpython-312.pyc
│   │       │   │   │           prepare.cpython-312.pyc
│   │       │   │   │           __init__.cpython-312.pyc
│   │       │   │   │
│   │       │   │   ├───req
│   │       │   │   │   │   constructors.py
│   │       │   │   │   │   req_file.py
│   │       │   │   │   │   req_install.py
│   │       │   │   │   │   req_set.py
│   │       │   │   │   │   req_uninstall.py
│   │       │   │   │   │   __init__.py
│   │       │   │   │   │
│   │       │   │   │   └───__pycache__
│   │       │   │   │           constructors.cpython-312.pyc
│   │       │   │   │           req_file.cpython-312.pyc
│   │       │   │   │           req_install.cpython-312.pyc
│   │       │   │   │           req_set.cpython-312.pyc
│   │       │   │   │           req_uninstall.cpython-312.pyc
│   │       │   │   │           __init__.cpython-312.pyc
│   │       │   │   │
│   │       │   │   ├───resolution
│   │       │   │   │   │   base.py
│   │       │   │   │   │   __init__.py
│   │       │   │   │   │
│   │       │   │   │   ├───legacy
│   │       │   │   │   │   │   resolver.py
│   │       │   │   │   │   │   __init__.py
│   │       │   │   │   │   │
│   │       │   │   │   │   └───__pycache__
│   │       │   │   │   │           resolver.cpython-312.pyc
│   │       │   │   │   │           __init__.cpython-312.pyc
│   │       │   │   │   │
│   │       │   │   │   ├───resolvelib
│   │       │   │   │   │   │   base.py
│   │       │   │   │   │   │   candidates.py
│   │       │   │   │   │   │   factory.py
│   │       │   │   │   │   │   found_candidates.py
│   │       │   │   │   │   │   provider.py
│   │       │   │   │   │   │   reporter.py
│   │       │   │   │   │   │   requirements.py
│   │       │   │   │   │   │   resolver.py
│   │       │   │   │   │   │   __init__.py
│   │       │   │   │   │   │
│   │       │   │   │   │   └───__pycache__
│   │       │   │   │   │           base.cpython-312.pyc
│   │       │   │   │   │           candidates.cpython-312.pyc
│   │       │   │   │   │           factory.cpython-312.pyc
│   │       │   │   │   │           found_candidates.cpython-312.pyc
│   │       │   │   │   │           provider.cpython-312.pyc
│   │       │   │   │   │           reporter.cpython-312.pyc
│   │       │   │   │   │           requirements.cpython-312.pyc
│   │       │   │   │   │           resolver.cpython-312.pyc
│   │       │   │   │   │           __init__.cpython-312.pyc
│   │       │   │   │   │
│   │       │   │   │   └───__pycache__
│   │       │   │   │           base.cpython-312.pyc
│   │       │   │   │           __init__.cpython-312.pyc
│   │       │   │   │
│   │       │   │   ├───utils
│   │       │   │   │   │   appdirs.py
│   │       │   │   │   │   compat.py
│   │       │   │   │   │   compatibility_tags.py
│   │       │   │   │   │   datetime.py
│   │       │   │   │   │   deprecation.py
│   │       │   │   │   │   direct_url_helpers.py
│   │       │   │   │   │   egg_link.py
│   │       │   │   │   │   encoding.py
│   │       │   │   │   │   entrypoints.py
│   │       │   │   │   │   filesystem.py
│   │       │   │   │   │   filetypes.py
│   │       │   │   │   │   glibc.py
│   │       │   │   │   │   hashes.py
│   │       │   │   │   │   logging.py
│   │       │   │   │   │   misc.py
│   │       │   │   │   │   models.py
│   │       │   │   │   │   packaging.py
│   │       │   │   │   │   setuptools_build.py
│   │       │   │   │   │   subprocess.py
│   │       │   │   │   │   temp_dir.py
│   │       │   │   │   │   unpacking.py
│   │       │   │   │   │   urls.py
│   │       │   │   │   │   virtualenv.py
│   │       │   │   │   │   wheel.py
│   │       │   │   │   │   _jaraco_text.py
│   │       │   │   │   │   _log.py
│   │       │   │   │   │   __init__.py
│   │       │   │   │   │
│   │       │   │   │   └───__pycache__
│   │       │   │   │           appdirs.cpython-312.pyc
│   │       │   │   │           compat.cpython-312.pyc
│   │       │   │   │           compatibility_tags.cpython-312.pyc
│   │       │   │   │           datetime.cpython-312.pyc
│   │       │   │   │           deprecation.cpython-312.pyc
│   │       │   │   │           direct_url_helpers.cpython-312.pyc
│   │       │   │   │           egg_link.cpython-312.pyc
│   │       │   │   │           encoding.cpython-312.pyc
│   │       │   │   │           entrypoints.cpython-312.pyc
│   │       │   │   │           filesystem.cpython-312.pyc
│   │       │   │   │           filetypes.cpython-312.pyc
│   │       │   │   │           glibc.cpython-312.pyc
│   │       │   │   │           hashes.cpython-312.pyc
│   │       │   │   │           logging.cpython-312.pyc
│   │       │   │   │           misc.cpython-312.pyc
│   │       │   │   │           models.cpython-312.pyc
│   │       │   │   │           packaging.cpython-312.pyc
│   │       │   │   │           setuptools_build.cpython-312.pyc
│   │       │   │   │           subprocess.cpython-312.pyc
│   │       │   │   │           temp_dir.cpython-312.pyc
│   │       │   │   │           unpacking.cpython-312.pyc
│   │       │   │   │           urls.cpython-312.pyc
│   │       │   │   │           virtualenv.cpython-312.pyc
│   │       │   │   │           wheel.cpython-312.pyc
│   │       │   │   │           _jaraco_text.cpython-312.pyc
│   │       │   │   │           _log.cpython-312.pyc
│   │       │   │   │           __init__.cpython-312.pyc
│   │       │   │   │
│   │       │   │   ├───vcs
│   │       │   │   │   │   bazaar.py
│   │       │   │   │   │   git.py
│   │       │   │   │   │   mercurial.py
│   │       │   │   │   │   subversion.py
│   │       │   │   │   │   versioncontrol.py
│   │       │   │   │   │   __init__.py
│   │       │   │   │   │
│   │       │   │   │   └───__pycache__
│   │       │   │   │           bazaar.cpython-312.pyc
│   │       │   │   │           git.cpython-312.pyc
│   │       │   │   │           mercurial.cpython-312.pyc
│   │       │   │   │           subversion.cpython-312.pyc
│   │       │   │   │           versioncontrol.cpython-312.pyc
│   │       │   │   │           __init__.cpython-312.pyc
│   │       │   │   │
│   │       │   │   └───__pycache__
│   │       │   │           build_env.cpython-312.pyc
│   │       │   │           cache.cpython-312.pyc
│   │       │   │           configuration.cpython-312.pyc
│   │       │   │           exceptions.cpython-312.pyc
│   │       │   │           main.cpython-312.pyc
│   │       │   │           pyproject.cpython-312.pyc
│   │       │   │           self_outdated_check.cpython-312.pyc
│   │       │   │           wheel_builder.cpython-312.pyc
│   │       │   │           __init__.cpython-312.pyc
│   │       │   │
│   │       │   ├───_vendor
│   │       │   │   │   six.py
│   │       │   │   │   typing_extensions.py
│   │       │   │   │   vendor.txt
│   │       │   │   │   __init__.py
│   │       │   │   │
│   │       │   │   ├───cachecontrol
│   │       │   │   │   │   adapter.py
│   │       │   │   │   │   cache.py
│   │       │   │   │   │   controller.py
│   │       │   │   │   │   filewrapper.py
│   │       │   │   │   │   heuristics.py
│   │       │   │   │   │   py.typed
│   │       │   │   │   │   serialize.py
│   │       │   │   │   │   wrapper.py
│   │       │   │   │   │   _cmd.py
│   │       │   │   │   │   __init__.py
│   │       │   │   │   │
│   │       │   │   │   ├───caches
│   │       │   │   │   │   │   file_cache.py
│   │       │   │   │   │   │   redis_cache.py
│   │       │   │   │   │   │   __init__.py
│   │       │   │   │   │   │
│   │       │   │   │   │   └───__pycache__
│   │       │   │   │   │           file_cache.cpython-312.pyc
│   │       │   │   │   │           redis_cache.cpython-312.pyc
│   │       │   │   │   │           __init__.cpython-312.pyc
│   │       │   │   │   │
│   │       │   │   │   └───__pycache__
│   │       │   │   │           adapter.cpython-312.pyc
│   │       │   │   │           cache.cpython-312.pyc
│   │       │   │   │           controller.cpython-312.pyc
│   │       │   │   │           filewrapper.cpython-312.pyc
│   │       │   │   │           heuristics.cpython-312.pyc
│   │       │   │   │           serialize.cpython-312.pyc
│   │       │   │   │           wrapper.cpython-312.pyc
│   │       │   │   │           _cmd.cpython-312.pyc
│   │       │   │   │           __init__.cpython-312.pyc
│   │       │   │   │
│   │       │   │   ├───certifi
│   │       │   │   │   │   cacert.pem
│   │       │   │   │   │   core.py
│   │       │   │   │   │   py.typed
│   │       │   │   │   │   __init__.py
│   │       │   │   │   │   __main__.py
│   │       │   │   │   │
│   │       │   │   │   └───__pycache__
│   │       │   │   │           core.cpython-312.pyc
│   │       │   │   │           __init__.cpython-312.pyc
│   │       │   │   │           __main__.cpython-312.pyc
│   │       │   │   │
│   │       │   │   ├───chardet
│   │       │   │   │   │   big5freq.py
│   │       │   │   │   │   big5prober.py
│   │       │   │   │   │   chardistribution.py
│   │       │   │   │   │   charsetgroupprober.py
│   │       │   │   │   │   charsetprober.py
│   │       │   │   │   │   codingstatemachine.py
│   │       │   │   │   │   codingstatemachinedict.py
│   │       │   │   │   │   cp949prober.py
│   │       │   │   │   │   enums.py
│   │       │   │   │   │   escprober.py
│   │       │   │   │   │   escsm.py
│   │       │   │   │   │   eucjpprober.py
│   │       │   │   │   │   euckrfreq.py
│   │       │   │   │   │   euckrprober.py
│   │       │   │   │   │   euctwfreq.py
│   │       │   │   │   │   euctwprober.py
│   │       │   │   │   │   gb2312freq.py
│   │       │   │   │   │   gb2312prober.py
│   │       │   │   │   │   hebrewprober.py
│   │       │   │   │   │   jisfreq.py
│   │       │   │   │   │   johabfreq.py
│   │       │   │   │   │   johabprober.py
│   │       │   │   │   │   jpcntx.py
│   │       │   │   │   │   langbulgarianmodel.py
│   │       │   │   │   │   langgreekmodel.py
│   │       │   │   │   │   langhebrewmodel.py
│   │       │   │   │   │   langhungarianmodel.py
│   │       │   │   │   │   langrussianmodel.py
│   │       │   │   │   │   langthaimodel.py
│   │       │   │   │   │   langturkishmodel.py
│   │       │   │   │   │   latin1prober.py
│   │       │   │   │   │   macromanprober.py
│   │       │   │   │   │   mbcharsetprober.py
│   │       │   │   │   │   mbcsgroupprober.py
│   │       │   │   │   │   mbcssm.py
│   │       │   │   │   │   py.typed
│   │       │   │   │   │   resultdict.py
│   │       │   │   │   │   sbcharsetprober.py
│   │       │   │   │   │   sbcsgroupprober.py
│   │       │   │   │   │   sjisprober.py
│   │       │   │   │   │   universaldetector.py
│   │       │   │   │   │   utf1632prober.py
│   │       │   │   │   │   utf8prober.py
│   │       │   │   │   │   version.py
│   │       │   │   │   │   __init__.py
│   │       │   │   │   │
│   │       │   │   │   ├───cli
│   │       │   │   │   │   │   chardetect.py
│   │       │   │   │   │   │   __init__.py
│   │       │   │   │   │   │
│   │       │   │   │   │   └───__pycache__
│   │       │   │   │   │           chardetect.cpython-312.pyc
│   │       │   │   │   │           __init__.cpython-312.pyc
│   │       │   │   │   │
│   │       │   │   │   ├───metadata
│   │       │   │   │   │   │   languages.py
│   │       │   │   │   │   │   __init__.py
│   │       │   │   │   │   │
│   │       │   │   │   │   └───__pycache__
│   │       │   │   │   │           languages.cpython-312.pyc
│   │       │   │   │   │           __init__.cpython-312.pyc
│   │       │   │   │   │
│   │       │   │   │   └───__pycache__
│   │       │   │   │           big5freq.cpython-312.pyc
│   │       │   │   │           big5prober.cpython-312.pyc
│   │       │   │   │           chardistribution.cpython-312.pyc
│   │       │   │   │           charsetgroupprober.cpython-312.pyc
│   │       │   │   │           charsetprober.cpython-312.pyc
│   │       │   │   │           codingstatemachine.cpython-312.pyc
│   │       │   │   │           codingstatemachinedict.cpython-312.pyc
│   │       │   │   │           cp949prober.cpython-312.pyc
│   │       │   │   │           enums.cpython-312.pyc
│   │       │   │   │           escprober.cpython-312.pyc
│   │       │   │   │           escsm.cpython-312.pyc
│   │       │   │   │           eucjpprober.cpython-312.pyc
│   │       │   │   │           euckrfreq.cpython-312.pyc
│   │       │   │   │           euckrprober.cpython-312.pyc
│   │       │   │   │           euctwfreq.cpython-312.pyc
│   │       │   │   │           euctwprober.cpython-312.pyc
│   │       │   │   │           gb2312freq.cpython-312.pyc
│   │       │   │   │           gb2312prober.cpython-312.pyc
│   │       │   │   │           hebrewprober.cpython-312.pyc
│   │       │   │   │           jisfreq.cpython-312.pyc
│   │       │   │   │           johabfreq.cpython-312.pyc
│   │       │   │   │           johabprober.cpython-312.pyc
│   │       │   │   │           jpcntx.cpython-312.pyc
│   │       │   │   │           langbulgarianmodel.cpython-312.pyc
│   │       │   │   │           langgreekmodel.cpython-312.pyc
│   │       │   │   │           langhebrewmodel.cpython-312.pyc
│   │       │   │   │           langhungarianmodel.cpython-312.pyc
│   │       │   │   │           langrussianmodel.cpython-312.pyc
│   │       │   │   │           langthaimodel.cpython-312.pyc
│   │       │   │   │           langturkishmodel.cpython-312.pyc
│   │       │   │   │           latin1prober.cpython-312.pyc
│   │       │   │   │           macromanprober.cpython-312.pyc
│   │       │   │   │           mbcharsetprober.cpython-312.pyc
│   │       │   │   │           mbcsgroupprober.cpython-312.pyc
│   │       │   │   │           mbcssm.cpython-312.pyc
│   │       │   │   │           resultdict.cpython-312.pyc
│   │       │   │   │           sbcharsetprober.cpython-312.pyc
│   │       │   │   │           sbcsgroupprober.cpython-312.pyc
│   │       │   │   │           sjisprober.cpython-312.pyc
│   │       │   │   │           universaldetector.cpython-312.pyc
│   │       │   │   │           utf1632prober.cpython-312.pyc
│   │       │   │   │           utf8prober.cpython-312.pyc
│   │       │   │   │           version.cpython-312.pyc
│   │       │   │   │           __init__.cpython-312.pyc
│   │       │   │   │
│   │       │   │   ├───colorama
│   │       │   │   │   │   ansi.py
│   │       │   │   │   │   ansitowin32.py
│   │       │   │   │   │   initialise.py
│   │       │   │   │   │   win32.py
│   │       │   │   │   │   winterm.py
│   │       │   │   │   │   __init__.py
│   │       │   │   │   │
│   │       │   │   │   ├───tests
│   │       │   │   │   │   │   ansitowin32_test.py
│   │       │   │   │   │   │   ansi_test.py
│   │       │   │   │   │   │   initialise_test.py
│   │       │   │   │   │   │   isatty_test.py
│   │       │   │   │   │   │   utils.py
│   │       │   │   │   │   │   winterm_test.py
│   │       │   │   │   │   │   __init__.py
│   │       │   │   │   │   │
│   │       │   │   │   │   └───__pycache__
│   │       │   │   │   │           ansitowin32_test.cpython-312.pyc
│   │       │   │   │   │           ansi_test.cpython-312.pyc
│   │       │   │   │   │           initialise_test.cpython-312.pyc
│   │       │   │   │   │           isatty_test.cpython-312.pyc
│   │       │   │   │   │           utils.cpython-312.pyc
│   │       │   │   │   │           winterm_test.cpython-312.pyc
│   │       │   │   │   │           __init__.cpython-312.pyc
│   │       │   │   │   │
│   │       │   │   │   └───__pycache__
│   │       │   │   │           ansi.cpython-312.pyc
│   │       │   │   │           ansitowin32.cpython-312.pyc
│   │       │   │   │           initialise.cpython-312.pyc
│   │       │   │   │           win32.cpython-312.pyc
│   │       │   │   │           winterm.cpython-312.pyc
│   │       │   │   │           __init__.cpython-312.pyc
│   │       │   │   │
│   │       │   │   ├───distlib
│   │       │   │   │   │   compat.py
│   │       │   │   │   │   database.py
│   │       │   │   │   │   index.py
│   │       │   │   │   │   locators.py
│   │       │   │   │   │   manifest.py
│   │       │   │   │   │   markers.py
│   │       │   │   │   │   metadata.py
│   │       │   │   │   │   resources.py
│   │       │   │   │   │   scripts.py
│   │       │   │   │   │   t32.exe
│   │       │   │   │   │   t64-arm.exe
│   │       │   │   │   │   t64.exe
│   │       │   │   │   │   util.py
│   │       │   │   │   │   version.py
│   │       │   │   │   │   w32.exe
│   │       │   │   │   │   w64-arm.exe
│   │       │   │   │   │   w64.exe
│   │       │   │   │   │   wheel.py
│   │       │   │   │   │   __init__.py
│   │       │   │   │   │
│   │       │   │   │   └───__pycache__
│   │       │   │   │           compat.cpython-312.pyc
│   │       │   │   │           database.cpython-312.pyc
│   │       │   │   │           index.cpython-312.pyc
│   │       │   │   │           locators.cpython-312.pyc
│   │       │   │   │           manifest.cpython-312.pyc
│   │       │   │   │           markers.cpython-312.pyc
│   │       │   │   │           metadata.cpython-312.pyc
│   │       │   │   │           resources.cpython-312.pyc
│   │       │   │   │           scripts.cpython-312.pyc
│   │       │   │   │           util.cpython-312.pyc
│   │       │   │   │           version.cpython-312.pyc
│   │       │   │   │           wheel.cpython-312.pyc
│   │       │   │   │           __init__.cpython-312.pyc
│   │       │   │   │
│   │       │   │   ├───distro
│   │       │   │   │   │   distro.py
│   │       │   │   │   │   py.typed
│   │       │   │   │   │   __init__.py
│   │       │   │   │   │   __main__.py
│   │       │   │   │   │
│   │       │   │   │   └───__pycache__
│   │       │   │   │           distro.cpython-312.pyc
│   │       │   │   │           __init__.cpython-312.pyc
│   │       │   │   │           __main__.cpython-312.pyc
│   │       │   │   │
│   │       │   │   ├───idna
│   │       │   │   │   │   codec.py
│   │       │   │   │   │   compat.py
│   │       │   │   │   │   core.py
│   │       │   │   │   │   idnadata.py
│   │       │   │   │   │   intranges.py
│   │       │   │   │   │   package_data.py
│   │       │   │   │   │   py.typed
│   │       │   │   │   │   uts46data.py
│   │       │   │   │   │   __init__.py
│   │       │   │   │   │
│   │       │   │   │   └───__pycache__
│   │       │   │   │           codec.cpython-312.pyc
│   │       │   │   │           compat.cpython-312.pyc
│   │       │   │   │           core.cpython-312.pyc
│   │       │   │   │           idnadata.cpython-312.pyc
│   │       │   │   │           intranges.cpython-312.pyc
│   │       │   │   │           package_data.cpython-312.pyc
│   │       │   │   │           uts46data.cpython-312.pyc
│   │       │   │   │           __init__.cpython-312.pyc
│   │       │   │   │
│   │       │   │   ├───msgpack
│   │       │   │   │   │   exceptions.py
│   │       │   │   │   │   ext.py
│   │       │   │   │   │   fallback.py
│   │       │   │   │   │   __init__.py
│   │       │   │   │   │
│   │       │   │   │   └───__pycache__
│   │       │   │   │           exceptions.cpython-312.pyc
│   │       │   │   │           ext.cpython-312.pyc
│   │       │   │   │           fallback.cpython-312.pyc
│   │       │   │   │           __init__.cpython-312.pyc
│   │       │   │   │
│   │       │   │   ├───packaging
│   │       │   │   │   │   markers.py
│   │       │   │   │   │   py.typed
│   │       │   │   │   │   requirements.py
│   │       │   │   │   │   specifiers.py
│   │       │   │   │   │   tags.py
│   │       │   │   │   │   utils.py
│   │       │   │   │   │   version.py
│   │       │   │   │   │   _manylinux.py
│   │       │   │   │   │   _musllinux.py
│   │       │   │   │   │   _structures.py
│   │       │   │   │   │   __about__.py
│   │       │   │   │   │   __init__.py
│   │       │   │   │   │
│   │       │   │   │   └───__pycache__
│   │       │   │   │           markers.cpython-312.pyc
│   │       │   │   │           requirements.cpython-312.pyc
│   │       │   │   │           specifiers.cpython-312.pyc
│   │       │   │   │           tags.cpython-312.pyc
│   │       │   │   │           utils.cpython-312.pyc
│   │       │   │   │           version.cpython-312.pyc
│   │       │   │   │           _manylinux.cpython-312.pyc
│   │       │   │   │           _musllinux.cpython-312.pyc
│   │       │   │   │           _structures.cpython-312.pyc
│   │       │   │   │           __about__.cpython-312.pyc
│   │       │   │   │           __init__.cpython-312.pyc
│   │       │   │   │
│   │       │   │   ├───pkg_resources
│   │       │   │   │   │   __init__.py
│   │       │   │   │   │
│   │       │   │   │   └───__pycache__
│   │       │   │   │           __init__.cpython-312.pyc
│   │       │   │   │
│   │       │   │   ├───platformdirs
│   │       │   │   │   │   android.py
│   │       │   │   │   │   api.py
│   │       │   │   │   │   macos.py
│   │       │   │   │   │   py.typed
│   │       │   │   │   │   unix.py
│   │       │   │   │   │   version.py
│   │       │   │   │   │   windows.py
│   │       │   │   │   │   __init__.py
│   │       │   │   │   │   __main__.py
│   │       │   │   │   │
│   │       │   │   │   └───__pycache__
│   │       │   │   │           android.cpython-312.pyc
│   │       │   │   │           api.cpython-312.pyc
│   │       │   │   │           macos.cpython-312.pyc
│   │       │   │   │           unix.cpython-312.pyc
│   │       │   │   │           version.cpython-312.pyc
│   │       │   │   │           windows.cpython-312.pyc
│   │       │   │   │           __init__.cpython-312.pyc
│   │       │   │   │           __main__.cpython-312.pyc
│   │       │   │   │
│   │       │   │   ├───pygments
│   │       │   │   │   │   cmdline.py
│   │       │   │   │   │   console.py
│   │       │   │   │   │   filter.py
│   │       │   │   │   │   formatter.py
│   │       │   │   │   │   lexer.py
│   │       │   │   │   │   modeline.py
│   │       │   │   │   │   plugin.py
│   │       │   │   │   │   regexopt.py
│   │       │   │   │   │   scanner.py
│   │       │   │   │   │   sphinxext.py
│   │       │   │   │   │   style.py
│   │       │   │   │   │   token.py
│   │       │   │   │   │   unistring.py
│   │       │   │   │   │   util.py
│   │       │   │   │   │   __init__.py
│   │       │   │   │   │   __main__.py
│   │       │   │   │   │
│   │       │   │   │   ├───filters
│   │       │   │   │   │   │   __init__.py
│   │       │   │   │   │   │
│   │       │   │   │   │   └───__pycache__
│   │       │   │   │   │           __init__.cpython-312.pyc
│   │       │   │   │   │
│   │       │   │   │   ├───formatters
│   │       │   │   │   │   │   bbcode.py
│   │       │   │   │   │   │   groff.py
│   │       │   │   │   │   │   html.py
│   │       │   │   │   │   │   img.py
│   │       │   │   │   │   │   irc.py
│   │       │   │   │   │   │   latex.py
│   │       │   │   │   │   │   other.py
│   │       │   │   │   │   │   pangomarkup.py
│   │       │   │   │   │   │   rtf.py
│   │       │   │   │   │   │   svg.py
│   │       │   │   │   │   │   terminal.py
│   │       │   │   │   │   │   terminal256.py
│   │       │   │   │   │   │   _mapping.py
│   │       │   │   │   │   │   __init__.py
│   │       │   │   │   │   │
│   │       │   │   │   │   └───__pycache__
│   │       │   │   │   │           bbcode.cpython-312.pyc
│   │       │   │   │   │           groff.cpython-312.pyc
│   │       │   │   │   │           html.cpython-312.pyc
│   │       │   │   │   │           img.cpython-312.pyc
│   │       │   │   │   │           irc.cpython-312.pyc
│   │       │   │   │   │           latex.cpython-312.pyc
│   │       │   │   │   │           other.cpython-312.pyc
│   │       │   │   │   │           pangomarkup.cpython-312.pyc
│   │       │   │   │   │           rtf.cpython-312.pyc
│   │       │   │   │   │           svg.cpython-312.pyc
│   │       │   │   │   │           terminal.cpython-312.pyc
│   │       │   │   │   │           terminal256.cpython-312.pyc
│   │       │   │   │   │           _mapping.cpython-312.pyc
│   │       │   │   │   │           __init__.cpython-312.pyc
│   │       │   │   │   │
│   │       │   │   │   ├───lexers
│   │       │   │   │   │   │   python.py
│   │       │   │   │   │   │   _mapping.py
│   │       │   │   │   │   │   __init__.py
│   │       │   │   │   │   │
│   │       │   │   │   │   └───__pycache__
│   │       │   │   │   │           python.cpython-312.pyc
│   │       │   │   │   │           _mapping.cpython-312.pyc
│   │       │   │   │   │           __init__.cpython-312.pyc
│   │       │   │   │   │
│   │       │   │   │   ├───styles
│   │       │   │   │   │   │   __init__.py
│   │       │   │   │   │   │
│   │       │   │   │   │   └───__pycache__
│   │       │   │   │   │           __init__.cpython-312.pyc
│   │       │   │   │   │
│   │       │   │   │   └───__pycache__
│   │       │   │   │           cmdline.cpython-312.pyc
│   │       │   │   │           console.cpython-312.pyc
│   │       │   │   │           filter.cpython-312.pyc
│   │       │   │   │           formatter.cpython-312.pyc
│   │       │   │   │           lexer.cpython-312.pyc
│   │       │   │   │           modeline.cpython-312.pyc
│   │       │   │   │           plugin.cpython-312.pyc
│   │       │   │   │           regexopt.cpython-312.pyc
│   │       │   │   │           scanner.cpython-312.pyc
│   │       │   │   │           sphinxext.cpython-312.pyc
│   │       │   │   │           style.cpython-312.pyc
│   │       │   │   │           token.cpython-312.pyc
│   │       │   │   │           unistring.cpython-312.pyc
│   │       │   │   │           util.cpython-312.pyc
│   │       │   │   │           __init__.cpython-312.pyc
│   │       │   │   │           __main__.cpython-312.pyc
│   │       │   │   │
│   │       │   │   ├───pyparsing
│   │       │   │   │   │   actions.py
│   │       │   │   │   │   common.py
│   │       │   │   │   │   core.py
│   │       │   │   │   │   exceptions.py
│   │       │   │   │   │   helpers.py
│   │       │   │   │   │   py.typed
│   │       │   │   │   │   results.py
│   │       │   │   │   │   testing.py
│   │       │   │   │   │   unicode.py
│   │       │   │   │   │   util.py
│   │       │   │   │   │   __init__.py
│   │       │   │   │   │
│   │       │   │   │   ├───diagram
│   │       │   │   │   │   │   __init__.py
│   │       │   │   │   │   │
│   │       │   │   │   │   └───__pycache__
│   │       │   │   │   │           __init__.cpython-312.pyc
│   │       │   │   │   │
│   │       │   │   │   └───__pycache__
│   │       │   │   │           actions.cpython-312.pyc
│   │       │   │   │           common.cpython-312.pyc
│   │       │   │   │           core.cpython-312.pyc
│   │       │   │   │           exceptions.cpython-312.pyc
│   │       │   │   │           helpers.cpython-312.pyc
│   │       │   │   │           results.cpython-312.pyc
│   │       │   │   │           testing.cpython-312.pyc
│   │       │   │   │           unicode.cpython-312.pyc
│   │       │   │   │           util.cpython-312.pyc
│   │       │   │   │           __init__.cpython-312.pyc
│   │       │   │   │
│   │       │   │   ├───pyproject_hooks
│   │       │   │   │   │   _compat.py
│   │       │   │   │   │   _impl.py
│   │       │   │   │   │   __init__.py
│   │       │   │   │   │
│   │       │   │   │   ├───_in_process
│   │       │   │   │   │   │   _in_process.py
│   │       │   │   │   │   │   __init__.py
│   │       │   │   │   │   │
│   │       │   │   │   │   └───__pycache__
│   │       │   │   │   │           _in_process.cpython-312.pyc
│   │       │   │   │   │           __init__.cpython-312.pyc
│   │       │   │   │   │
│   │       │   │   │   └───__pycache__
│   │       │   │   │           _compat.cpython-312.pyc
│   │       │   │   │           _impl.cpython-312.pyc
│   │       │   │   │           __init__.cpython-312.pyc
│   │       │   │   │
│   │       │   │   ├───requests
│   │       │   │   │   │   adapters.py
│   │       │   │   │   │   api.py
│   │       │   │   │   │   auth.py
│   │       │   │   │   │   certs.py
│   │       │   │   │   │   compat.py
│   │       │   │   │   │   cookies.py
│   │       │   │   │   │   exceptions.py
│   │       │   │   │   │   help.py
│   │       │   │   │   │   hooks.py
│   │       │   │   │   │   models.py
│   │       │   │   │   │   packages.py
│   │       │   │   │   │   sessions.py
│   │       │   │   │   │   status_codes.py
│   │       │   │   │   │   structures.py
│   │       │   │   │   │   utils.py
│   │       │   │   │   │   _internal_utils.py
│   │       │   │   │   │   __init__.py
│   │       │   │   │   │   __version__.py
│   │       │   │   │   │
│   │       │   │   │   └───__pycache__
│   │       │   │   │           adapters.cpython-312.pyc
│   │       │   │   │           api.cpython-312.pyc
│   │       │   │   │           auth.cpython-312.pyc
│   │       │   │   │           certs.cpython-312.pyc
│   │       │   │   │           compat.cpython-312.pyc
│   │       │   │   │           cookies.cpython-312.pyc
│   │       │   │   │           exceptions.cpython-312.pyc
│   │       │   │   │           help.cpython-312.pyc
│   │       │   │   │           hooks.cpython-312.pyc
│   │       │   │   │           models.cpython-312.pyc
│   │       │   │   │           packages.cpython-312.pyc
│   │       │   │   │           sessions.cpython-312.pyc
│   │       │   │   │           status_codes.cpython-312.pyc
│   │       │   │   │           structures.cpython-312.pyc
│   │       │   │   │           utils.cpython-312.pyc
│   │       │   │   │           _internal_utils.cpython-312.pyc
│   │       │   │   │           __init__.cpython-312.pyc
│   │       │   │   │           __version__.cpython-312.pyc
│   │       │   │   │
│   │       │   │   ├───resolvelib
│   │       │   │   │   │   providers.py
│   │       │   │   │   │   py.typed
│   │       │   │   │   │   reporters.py
│   │       │   │   │   │   resolvers.py
│   │       │   │   │   │   structs.py
│   │       │   │   │   │   __init__.py
│   │       │   │   │   │
│   │       │   │   │   ├───compat
│   │       │   │   │   │   │   collections_abc.py
│   │       │   │   │   │   │   __init__.py
│   │       │   │   │   │   │
│   │       │   │   │   │   └───__pycache__
│   │       │   │   │   │           collections_abc.cpython-312.pyc
│   │       │   │   │   │           __init__.cpython-312.pyc
│   │       │   │   │   │
│   │       │   │   │   └───__pycache__
│   │       │   │   │           providers.cpython-312.pyc
│   │       │   │   │           reporters.cpython-312.pyc
│   │       │   │   │           resolvers.cpython-312.pyc
│   │       │   │   │           structs.cpython-312.pyc
│   │       │   │   │           __init__.cpython-312.pyc
│   │       │   │   │
│   │       │   │   ├───rich
│   │       │   │   │   │   abc.py
│   │       │   │   │   │   align.py
│   │       │   │   │   │   ansi.py
│   │       │   │   │   │   bar.py
│   │       │   │   │   │   box.py
│   │       │   │   │   │   cells.py
│   │       │   │   │   │   color.py
│   │       │   │   │   │   color_triplet.py
│   │       │   │   │   │   columns.py
│   │       │   │   │   │   console.py
│   │       │   │   │   │   constrain.py
│   │       │   │   │   │   containers.py
│   │       │   │   │   │   control.py
│   │       │   │   │   │   default_styles.py
│   │       │   │   │   │   diagnose.py
│   │       │   │   │   │   emoji.py
│   │       │   │   │   │   errors.py
│   │       │   │   │   │   filesize.py
│   │       │   │   │   │   file_proxy.py
│   │       │   │   │   │   highlighter.py
│   │       │   │   │   │   json.py
│   │       │   │   │   │   jupyter.py
│   │       │   │   │   │   layout.py
│   │       │   │   │   │   live.py
│   │       │   │   │   │   live_render.py
│   │       │   │   │   │   logging.py
│   │       │   │   │   │   markup.py
│   │       │   │   │   │   measure.py
│   │       │   │   │   │   padding.py
│   │       │   │   │   │   pager.py
│   │       │   │   │   │   palette.py
│   │       │   │   │   │   panel.py
│   │       │   │   │   │   pretty.py
│   │       │   │   │   │   progress.py
│   │       │   │   │   │   progress_bar.py
│   │       │   │   │   │   prompt.py
│   │       │   │   │   │   protocol.py
│   │       │   │   │   │   py.typed
│   │       │   │   │   │   region.py
│   │       │   │   │   │   repr.py
│   │       │   │   │   │   rule.py
│   │       │   │   │   │   scope.py
│   │       │   │   │   │   screen.py
│   │       │   │   │   │   segment.py
│   │       │   │   │   │   spinner.py
│   │       │   │   │   │   status.py
│   │       │   │   │   │   style.py
│   │       │   │   │   │   styled.py
│   │       │   │   │   │   syntax.py
│   │       │   │   │   │   table.py
│   │       │   │   │   │   terminal_theme.py
│   │       │   │   │   │   text.py
│   │       │   │   │   │   theme.py
│   │       │   │   │   │   themes.py
│   │       │   │   │   │   traceback.py
│   │       │   │   │   │   tree.py
│   │       │   │   │   │   _cell_widths.py
│   │       │   │   │   │   _emoji_codes.py
│   │       │   │   │   │   _emoji_replace.py
│   │       │   │   │   │   _export_format.py
│   │       │   │   │   │   _extension.py
│   │       │   │   │   │   _fileno.py
│   │       │   │   │   │   _inspect.py
│   │       │   │   │   │   _log_render.py
│   │       │   │   │   │   _loop.py
│   │       │   │   │   │   _null_file.py
│   │       │   │   │   │   _palettes.py
│   │       │   │   │   │   _pick.py
│   │       │   │   │   │   _ratio.py
│   │       │   │   │   │   _spinners.py
│   │       │   │   │   │   _stack.py
│   │       │   │   │   │   _timer.py
│   │       │   │   │   │   _win32_console.py
│   │       │   │   │   │   _windows.py
│   │       │   │   │   │   _windows_renderer.py
│   │       │   │   │   │   _wrap.py
│   │       │   │   │   │   __init__.py
│   │       │   │   │   │   __main__.py
│   │       │   │   │   │
│   │       │   │   │   └───__pycache__
│   │       │   │   │           abc.cpython-312.pyc
│   │       │   │   │           align.cpython-312.pyc
│   │       │   │   │           ansi.cpython-312.pyc
│   │       │   │   │           bar.cpython-312.pyc
│   │       │   │   │           box.cpython-312.pyc
│   │       │   │   │           cells.cpython-312.pyc
│   │       │   │   │           color.cpython-312.pyc
│   │       │   │   │           color_triplet.cpython-312.pyc
│   │       │   │   │           columns.cpython-312.pyc
│   │       │   │   │           console.cpython-312.pyc
│   │       │   │   │           constrain.cpython-312.pyc
│   │       │   │   │           containers.cpython-312.pyc
│   │       │   │   │           control.cpython-312.pyc
│   │       │   │   │           default_styles.cpython-312.pyc
│   │       │   │   │           diagnose.cpython-312.pyc
│   │       │   │   │           emoji.cpython-312.pyc
│   │       │   │   │           errors.cpython-312.pyc
│   │       │   │   │           filesize.cpython-312.pyc
│   │       │   │   │           file_proxy.cpython-312.pyc
│   │       │   │   │           highlighter.cpython-312.pyc
│   │       │   │   │           json.cpython-312.pyc
│   │       │   │   │           jupyter.cpython-312.pyc
│   │       │   │   │           layout.cpython-312.pyc
│   │       │   │   │           live.cpython-312.pyc
│   │       │   │   │           live_render.cpython-312.pyc
│   │       │   │   │           logging.cpython-312.pyc
│   │       │   │   │           markup.cpython-312.pyc
│   │       │   │   │           measure.cpython-312.pyc
│   │       │   │   │           padding.cpython-312.pyc
│   │       │   │   │           pager.cpython-312.pyc
│   │       │   │   │           palette.cpython-312.pyc
│   │       │   │   │           panel.cpython-312.pyc
│   │       │   │   │           pretty.cpython-312.pyc
│   │       │   │   │           progress.cpython-312.pyc
│   │       │   │   │           progress_bar.cpython-312.pyc
│   │       │   │   │           prompt.cpython-312.pyc
│   │       │   │   │           protocol.cpython-312.pyc
│   │       │   │   │           region.cpython-312.pyc
│   │       │   │   │           repr.cpython-312.pyc
│   │       │   │   │           rule.cpython-312.pyc
│   │       │   │   │           scope.cpython-312.pyc
│   │       │   │   │           screen.cpython-312.pyc
│   │       │   │   │           segment.cpython-312.pyc
│   │       │   │   │           spinner.cpython-312.pyc
│   │       │   │   │           status.cpython-312.pyc
│   │       │   │   │           style.cpython-312.pyc
│   │       │   │   │           styled.cpython-312.pyc
│   │       │   │   │           syntax.cpython-312.pyc
│   │       │   │   │           table.cpython-312.pyc
│   │       │   │   │           terminal_theme.cpython-312.pyc
│   │       │   │   │           text.cpython-312.pyc
│   │       │   │   │           theme.cpython-312.pyc
│   │       │   │   │           themes.cpython-312.pyc
│   │       │   │   │           traceback.cpython-312.pyc
│   │       │   │   │           tree.cpython-312.pyc
│   │       │   │   │           _cell_widths.cpython-312.pyc
│   │       │   │   │           _emoji_codes.cpython-312.pyc
│   │       │   │   │           _emoji_replace.cpython-312.pyc
│   │       │   │   │           _export_format.cpython-312.pyc
│   │       │   │   │           _extension.cpython-312.pyc
│   │       │   │   │           _fileno.cpython-312.pyc
│   │       │   │   │           _inspect.cpython-312.pyc
│   │       │   │   │           _log_render.cpython-312.pyc
│   │       │   │   │           _loop.cpython-312.pyc
│   │       │   │   │           _null_file.cpython-312.pyc
│   │       │   │   │           _palettes.cpython-312.pyc
│   │       │   │   │           _pick.cpython-312.pyc
│   │       │   │   │           _ratio.cpython-312.pyc
│   │       │   │   │           _spinners.cpython-312.pyc
│   │       │   │   │           _stack.cpython-312.pyc
│   │       │   │   │           _timer.cpython-312.pyc
│   │       │   │   │           _win32_console.cpython-312.pyc
│   │       │   │   │           _windows.cpython-312.pyc
│   │       │   │   │           _windows_renderer.cpython-312.pyc
│   │       │   │   │           _wrap.cpython-312.pyc
│   │       │   │   │           __init__.cpython-312.pyc
│   │       │   │   │           __main__.cpython-312.pyc
│   │       │   │   │
│   │       │   │   ├───tenacity
│   │       │   │   │   │   after.py
│   │       │   │   │   │   before.py
│   │       │   │   │   │   before_sleep.py
│   │       │   │   │   │   nap.py
│   │       │   │   │   │   py.typed
│   │       │   │   │   │   retry.py
│   │       │   │   │   │   stop.py
│   │       │   │   │   │   tornadoweb.py
│   │       │   │   │   │   wait.py
│   │       │   │   │   │   _asyncio.py
│   │       │   │   │   │   _utils.py
│   │       │   │   │   │   __init__.py
│   │       │   │   │   │
│   │       │   │   │   └───__pycache__
│   │       │   │   │           after.cpython-312.pyc
│   │       │   │   │           before.cpython-312.pyc
│   │       │   │   │           before_sleep.cpython-312.pyc
│   │       │   │   │           nap.cpython-312.pyc
│   │       │   │   │           retry.cpython-312.pyc
│   │       │   │   │           stop.cpython-312.pyc
│   │       │   │   │           tornadoweb.cpython-312.pyc
│   │       │   │   │           wait.cpython-312.pyc
│   │       │   │   │           _asyncio.cpython-312.pyc
│   │       │   │   │           _utils.cpython-312.pyc
│   │       │   │   │           __init__.cpython-312.pyc
│   │       │   │   │
│   │       │   │   ├───tomli
│   │       │   │   │   │   py.typed
│   │       │   │   │   │   _parser.py
│   │       │   │   │   │   _re.py
│   │       │   │   │   │   _types.py
│   │       │   │   │   │   __init__.py
│   │       │   │   │   │
│   │       │   │   │   └───__pycache__
│   │       │   │   │           _parser.cpython-312.pyc
│   │       │   │   │           _re.cpython-312.pyc
│   │       │   │   │           _types.cpython-312.pyc
│   │       │   │   │           __init__.cpython-312.pyc
│   │       │   │   │
│   │       │   │   ├───truststore
│   │       │   │   │   │   py.typed
│   │       │   │   │   │   _api.py
│   │       │   │   │   │   _macos.py
│   │       │   │   │   │   _openssl.py
│   │       │   │   │   │   _ssl_constants.py
│   │       │   │   │   │   _windows.py
│   │       │   │   │   │   __init__.py
│   │       │   │   │   │
│   │       │   │   │   └───__pycache__
│   │       │   │   │           _api.cpython-312.pyc
│   │       │   │   │           _macos.cpython-312.pyc
│   │       │   │   │           _openssl.cpython-312.pyc
│   │       │   │   │           _ssl_constants.cpython-312.pyc
│   │       │   │   │           _windows.cpython-312.pyc
│   │       │   │   │           __init__.cpython-312.pyc
│   │       │   │   │
│   │       │   │   ├───urllib3
│   │       │   │   │   │   connection.py
│   │       │   │   │   │   connectionpool.py
│   │       │   │   │   │   exceptions.py
│   │       │   │   │   │   fields.py
│   │       │   │   │   │   filepost.py
│   │       │   │   │   │   poolmanager.py
│   │       │   │   │   │   request.py
│   │       │   │   │   │   response.py
│   │       │   │   │   │   _collections.py
│   │       │   │   │   │   _version.py
│   │       │   │   │   │   __init__.py
│   │       │   │   │   │
│   │       │   │   │   ├───contrib
│   │       │   │   │   │   │   appengine.py
│   │       │   │   │   │   │   ntlmpool.py
│   │       │   │   │   │   │   pyopenssl.py
│   │       │   │   │   │   │   securetransport.py
│   │       │   │   │   │   │   socks.py
│   │       │   │   │   │   │   _appengine_environ.py
│   │       │   │   │   │   │   __init__.py
│   │       │   │   │   │   │
│   │       │   │   │   │   ├───_securetransport
│   │       │   │   │   │   │   │   bindings.py
│   │       │   │   │   │   │   │   low_level.py
│   │       │   │   │   │   │   │   __init__.py
│   │       │   │   │   │   │   │
│   │       │   │   │   │   │   └───__pycache__
│   │       │   │   │   │   │           bindings.cpython-312.pyc
│   │       │   │   │   │   │           low_level.cpython-312.pyc
│   │       │   │   │   │   │           __init__.cpython-312.pyc
│   │       │   │   │   │   │
│   │       │   │   │   │   └───__pycache__
│   │       │   │   │   │           appengine.cpython-312.pyc
│   │       │   │   │   │           ntlmpool.cpython-312.pyc
│   │       │   │   │   │           pyopenssl.cpython-312.pyc
│   │       │   │   │   │           securetransport.cpython-312.pyc
│   │       │   │   │   │           socks.cpython-312.pyc
│   │       │   │   │   │           _appengine_environ.cpython-312.pyc
│   │       │   │   │   │           __init__.cpython-312.pyc
│   │       │   │   │   │
│   │       │   │   │   ├───packages
│   │       │   │   │   │   │   six.py
│   │       │   │   │   │   │   __init__.py
│   │       │   │   │   │   │
│   │       │   │   │   │   ├───backports
│   │       │   │   │   │   │   │   makefile.py
│   │       │   │   │   │   │   │   weakref_finalize.py
│   │       │   │   │   │   │   │   __init__.py
│   │       │   │   │   │   │   │
│   │       │   │   │   │   │   └───__pycache__
│   │       │   │   │   │   │           makefile.cpython-312.pyc
│   │       │   │   │   │   │           weakref_finalize.cpython-312.pyc
│   │       │   │   │   │   │           __init__.cpython-312.pyc
│   │       │   │   │   │   │
│   │       │   │   │   │   └───__pycache__
│   │       │   │   │   │           six.cpython-312.pyc
│   │       │   │   │   │           __init__.cpython-312.pyc
│   │       │   │   │   │
│   │       │   │   │   ├───util
│   │       │   │   │   │   │   connection.py
│   │       │   │   │   │   │   proxy.py
│   │       │   │   │   │   │   queue.py
│   │       │   │   │   │   │   request.py
│   │       │   │   │   │   │   response.py
│   │       │   │   │   │   │   retry.py
│   │       │   │   │   │   │   ssltransport.py
│   │       │   │   │   │   │   ssl_.py
│   │       │   │   │   │   │   ssl_match_hostname.py
│   │       │   │   │   │   │   timeout.py
│   │       │   │   │   │   │   url.py
│   │       │   │   │   │   │   wait.py
│   │       │   │   │   │   │   __init__.py
│   │       │   │   │   │   │
│   │       │   │   │   │   └───__pycache__
│   │       │   │   │   │           connection.cpython-312.pyc
│   │       │   │   │   │           proxy.cpython-312.pyc
│   │       │   │   │   │           queue.cpython-312.pyc
│   │       │   │   │   │           request.cpython-312.pyc
│   │       │   │   │   │           response.cpython-312.pyc
│   │       │   │   │   │           retry.cpython-312.pyc
│   │       │   │   │   │           ssltransport.cpython-312.pyc
│   │       │   │   │   │           ssl_.cpython-312.pyc
│   │       │   │   │   │           ssl_match_hostname.cpython-312.pyc
│   │       │   │   │   │           timeout.cpython-312.pyc
│   │       │   │   │   │           url.cpython-312.pyc
│   │       │   │   │   │           wait.cpython-312.pyc
│   │       │   │   │   │           __init__.cpython-312.pyc
│   │       │   │   │   │
│   │       │   │   │   └───__pycache__
│   │       │   │   │           connection.cpython-312.pyc
│   │       │   │   │           connectionpool.cpython-312.pyc
│   │       │   │   │           exceptions.cpython-312.pyc
│   │       │   │   │           fields.cpython-312.pyc
│   │       │   │   │           filepost.cpython-312.pyc
│   │       │   │   │           poolmanager.cpython-312.pyc
│   │       │   │   │           request.cpython-312.pyc
│   │       │   │   │           response.cpython-312.pyc
│   │       │   │   │           _collections.cpython-312.pyc
│   │       │   │   │           _version.cpython-312.pyc
│   │       │   │   │           __init__.cpython-312.pyc
│   │       │   │   │
│   │       │   │   ├───webencodings
│   │       │   │   │   │   labels.py
│   │       │   │   │   │   mklabels.py
│   │       │   │   │   │   tests.py
│   │       │   │   │   │   x_user_defined.py
│   │       │   │   │   │   __init__.py
│   │       │   │   │   │
│   │       │   │   │   └───__pycache__
│   │       │   │   │           labels.cpython-312.pyc
│   │       │   │   │           mklabels.cpython-312.pyc
│   │       │   │   │           tests.cpython-312.pyc
│   │       │   │   │           x_user_defined.cpython-312.pyc
│   │       │   │   │           __init__.cpython-312.pyc
│   │       │   │   │
│   │       │   │   └───__pycache__
│   │       │   │           six.cpython-312.pyc
│   │       │   │           typing_extensions.cpython-312.pyc
│   │       │   │           __init__.cpython-312.pyc
│   │       │   │
│   │       │   └───__pycache__
│   │       │           __init__.cpython-312.pyc
│   │       │           __main__.cpython-312.pyc
│   │       │           __pip-runner__.cpython-312.pyc
│   │       │
│   │       └───pip-24.0.dist-info
│   │               AUTHORS.txt
│   │               entry_points.txt
│   │               INSTALLER
│   │               LICENSE.txt
│   │               METADATA
│   │               RECORD
│   │               REQUESTED
│   │               top_level.txt
│   │               WHEEL
│   │
│   └───Scripts
│           activate
│           activate.bat
│           Activate.ps1
│           deactivate.bat
│           pip.exe
│           pip3.12.exe
│           pip3.exe
│           python.exe
│           pythonw.exe
│
├───app
│   │   bi.py
│   │   clean.py
│   │   etl.py
│   │   export_parquet.py
│   │   nl2sql_simple.py
│   │   report.py
│   │   runner.py
│   │   scheduler.py
│   │   serve.py
│   │   sources.py
│   │   status.py
│   │   utils.py
│   │   __init__.py
│   │   __main__.py
│   │
│   ├───adapters
│   │   │   base.py
│   │   │   csv_local.py
│   │   │   http_json.py
│   │   │
│   │   └───__pycache__
│   │           base.cpython-311.pyc
│   │           base.cpython-312.pyc
│   │           csv_local.cpython-311.pyc
│   │           csv_local.cpython-312.pyc
│   │           http_json.cpython-311.pyc
│   │           http_json.cpython-312.pyc
│   │
│   ├───sources
│   │   │   github.py
│   │   │   openmeteo_air.py
│   │   │   usgs.py
│   │   │   worldbank.py
│   │   │   __init__.py
│   │   │
│   │   └───__pycache__
│   │           github.cpython-311.pyc
│   │           openaq.cpython-311.pyc
│   │           openmeteo_air.cpython-311.pyc
│   │           usgs.cpython-311.pyc
│   │           worldbank.cpython-311.pyc
│   │           __init__.cpython-311.pyc
│   │
│   └───__pycache__
│           bi.cpython-311.pyc
│           clean.cpython-311.pyc
│           etl.cpython-311.pyc
│           etl.cpython-312.pyc
│           export_parquet.cpython-311.pyc
│           nl2sql_simple.cpython-312.pyc
│           report.cpython-311.pyc
│           runner.cpython-311.pyc
│           runner.cpython-312.pyc
│           sources.cpython-311.pyc
│           status.cpython-311.pyc
│           status.cpython-312.pyc
│           utils.cpython-311.pyc
│           __init__.cpython-312.pyc
│
├───config
│       dq.yml
│       settings.toml
│       sources.yml
│
├───data
│   │   .gitkeep
│   │   etl.db
│   │   warehouse.duckdb
│   │
│   ├───input
│   │       .gitkeep
│   │       ventas.csv
│   │
│   ├───parquet
│   ├───plots
│   └───reports
│           github_gh_openai_openai_python_20250812_134536.csv
│           health_20250812_153924.json
│           health_20250812_154326.json
│           health_20250813_121508.json
│           health_20250819_142724.json
│           health_20250819_181930.json
│           health_20250821_133952.json
│           health_20250821_134715.json
│           health_20250821_134737.json
│           health_20250821_171319.json
│
├───docs
│       HANDOVER_NOW.md
│
├───scripts
│       bootstrap_dev.sh
│
└───tests
    │   test_v04_bigmixed_full.py
    │   test_v04_bigmixed_reduced.py
    │   test_v04_cornercases.py
    │   test_v04_duplicates.py
    │   test_v04_extreme.py
    │   test_v04_nulls.py
    │   test_v04_partitioning.py
    │   test_v04_poc.py
    │   test_v04_population.py
    │   test_v04_stress.py
    │   test_v04_types.py
    │
    └───__pycache__
            test_v04_bigmixed_full.cpython-311.pyc
            test_v04_bigmixed_reduced.cpython-311.pyc
            test_v04_cornercases.cpython-311.pyc
            test_v04_duplicates.cpython-311.pyc
            test_v04_extreme.cpython-311.pyc
            test_v04_nulls.cpython-311.pyc
            test_v04_partitioning.cpython-311.pyc
            test_v04_poc.cpython-311.pyc
            test_v04_population.cpython-311.pyc
            test_v04_stress.cpython-311.pyc
            test_v04_types.cpython-311.pyc