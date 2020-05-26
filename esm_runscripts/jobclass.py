import six


class jobclass:

    relevant_files = []
    filetype_specific_dict = {}

    def __init__(self, job_type):

        import esm_rcfile

        self.recipefile = (
            esm_rcfile.FUNCTION_PATH + "/esm_runscripts/esm_runscripts.yaml"
        )
        self.pluginsfile = esm_rcfile.FUNCTION_PATH + "/esm_runscripts/esm_plugins.yaml"

        import esm_plugin_manager

        self.framework_recipe = esm_plugin_manager.read_recipe(
            self.recipefile, {"job_type": job_type}
        )
        self.framework_plugins = esm_plugin_manager.read_plugin_information(
            self.pluginsfile, self.framework_recipe
        )
        esm_plugin_manager.check_plugin_availability(self.framework_plugins)

    def evaluate(self, config):
        import esm_plugin_manager

        config = esm_plugin_manager.work_through_recipe(
            self.framework_recipe, self.framework_plugins, config
        )
        return config

    #########################################################################################
    #                                   general stuff                                       #
    #########################################################################################

    def assemble_file_lists(self, config, filetypes):
        all_files_to_copy = []
        six.print_("\n" "- Generating file lists for this run...")
        for model in config["general"]["valid_model_names"]:
            six.print_("-" * 80)
            six.print_("* %s" % config[model]["model"], "\n")
            (
                all_component_files,
                filetype_specific_dict,
            ) = self.really_assemble_file_list(config, model, filetypes)

            self.filetype_specific_dict[model] = filetype_specific_dict
            all_files_to_copy += all_component_files
        return all_files_to_copy

    @staticmethod
    def print_used_files(config):

        self = config["general"]["jobclass"]
        for model in self.filetype_specific_dict:
            with open(
                config[model]["thisrun_config_dir"]
                + "/"
                + config["general"]["expid"]
                + "_filelist_"
                + config["general"]["run_datestamp"],
                "w",
            ) as flist:
                flist.write(
                    "These files are used for \nexperiment %s\ncomponent %s\ndate %s"
                    % (
                        config["general"]["expid"],
                        config[model]["model"],
                        config["general"]["run_datestamp"],
                    )
                )
                flist.write("\n")
                flist.write(80 * "-")
                for filetype in self.filetype_specific_dict[model]:
                    flist.write("\n" + filetype.upper() + ":\n")
                    for (
                        source,
                        exp_tree,
                        exp_name,
                        work_dir_name,
                        subfolder,
                    ) in self.filetype_specific_dict[model][filetype]:
                        flist.write("\nSource: " + source)
                        flist.write("\nExp Tree: " + exp_tree + subfolder + exp_name)
                        flist.write("\nWork Dir: " + subfolder + work_dir_name)
                        flist.write("\n")
                        print("-  " + subfolder + work_dir_name + ": " + source)
                    flist.write("\n")
                    flist.write(80 * "-")

    def really_assemble_file_list(self, config, model, filetypes):
        import glob
        import copy
        import logging
        import os

        modelconfig = config[model]
        general_config = config["general"]

        # print (model)
        # import esm_parser
        # esm_parser.pprint_config(modelconfig)
        # sys.exit(0)

        all_files_to_process = []
        filetype_files_for_list = {}
        for filetype in filetypes:
            filetype_files = []

            if filetype == "restart_in" and not modelconfig["lresume"]:
                six.print_(
                    "- restart files do not make sense for a cold start, skipping..."
                )
                continue
            if filetype + "_sources" not in modelconfig:
                continue

            ####### start globbing here

            inverted_dict = {}
            if filetype + "_files" in modelconfig:
                for k, v in six.iteritems(modelconfig[filetype + "_files"]):
                    inverted_dict[v] = k

            sources_dict = copy.deepcopy(modelconfig[filetype + "_sources"])

            for file_descriptor, file_source in six.iteritems(sources_dict):
                if "*" in file_source:
                    # esm_parser.pprint_config(modelconfig)
                    file_category = None
                    subfolder = None
                    if filetype + "_files" in modelconfig:
                        if file_descriptor in modelconfig[filetype + "_files"]:
                            file_category = inverted_dict[file_descriptor]
                    if filetype + "_in_work" in modelconfig:
                        if file_descriptor in modelconfig[filetype + "_in_work"]:
                            subfolder = modelconfig[filetype + "_in_work"][
                                file_descriptor
                            ].replace("*", "")
                            if not subfolder.endswith("/"):
                                subfolder = subfolder + "/"
                    all_file_sources = glob.glob(file_source)

                    running_index = 0
                    for new_source in all_file_sources:
                        running_index += 1
                        new_descriptor = file_descriptor + "_" + str(running_index)
                        modelconfig[filetype + "_sources"][new_descriptor] = new_source
                        if file_category:
                            new_category = file_category + "_" + str(running_index)
                            modelconfig[filetype + "_files"][
                                new_category
                            ] = new_descriptor
                        if subfolder:
                            new_in_work = subfolder + new_source.rsplit("/", 1)[-1]
                            modelconfig[filetype + "_in_work"][
                                new_descriptor
                            ] = new_in_work

                    del modelconfig[filetype + "_sources"][file_descriptor]
                    if file_category:
                        del modelconfig[filetype + "_files"][file_category]
                    if subfolder:
                        del modelconfig[filetype + "_in_work"][file_descriptor]

            ######## end globbing stuff

            filedir_intermediate = modelconfig["thisrun_" + filetype + "_dir"]
            for file_descriptor, file_source in six.iteritems(
                modelconfig[filetype + "_sources"]
            ):
                if filetype == "restart_in":
                    file_source = (
                        modelconfig["parent_restart_dir"]
                        + "/"
                        + os.path.basename(file_source)
                    )
                logging.debug(
                    "file_descriptor=%s, file_source=%s", file_descriptor, file_source
                )
                if filetype + "_files" in modelconfig:
                    if file_descriptor not in modelconfig[filetype + "_files"].values():
                        continue
                    else:
                        inverted_dict = {}
                        for k, v in six.iteritems(modelconfig[filetype + "_files"]):
                            inverted_dict[v] = k
                        file_category = inverted_dict[file_descriptor]
                else:
                    file_category = file_descriptor

                logging.debug(type(file_source))

                # should be generalized to all sorts of dates on day

                all_years = [general_config["current_date"].year]
                if (
                    filetype + "_additional_information" in modelconfig
                    and file_category
                    in modelconfig[filetype + "_additional_information"]
                ):
                    if (
                        "need_timestep_before"
                        in modelconfig[filetype + "_additional_information"][
                            file_category
                        ]
                    ):
                        all_years.append(general_config["prev_date"].year)
                    if (
                        "need_timestep_after"
                        in modelconfig[filetype + "_additional_information"][
                            file_category
                        ]
                    ):
                        all_years.append(general_config["next_date"].year)
                    if (
                        "need_year_before"
                        in modelconfig[filetype + "_additional_information"][
                            file_category
                        ]
                    ):
                        all_years.append(general_config["current_date"].year - 1)
                    if (
                        "need_year_after"
                        in modelconfig[filetype + "_additional_information"][
                            file_category
                        ]
                    ):
                        all_years.append(general_config["next_date"].year + 1)

                all_years = list(dict.fromkeys(all_years))  # removes duplicates

                if (
                    filetype + "_in_work" in modelconfig
                    and file_category in modelconfig[filetype + "_in_work"].keys()
                ):
                    target_name = modelconfig[filetype + "_in_work"][file_category]
                else:
                    target_name = os.path.basename(file_source)

                for year in all_years:

                    this_target_name = target_name.replace("@YEAR@", str(year))
                    source_name = self.find_correct_source(file_source, year)
                    file_target = filedir_intermediate + "/" + this_target_name

                    if "/" in this_target_name:
                        subfolder = this_target_name.rsplit("/", 1)[0] + "/"
                    else:
                        subfolder = ""

                    filetype_files.append(
                        (
                            source_name,
                            filedir_intermediate,
                            os.path.basename(source_name),
                            this_target_name.rsplit("/", 1)[-1],
                            subfolder,
                        )
                    )

            filetype_files_for_list[filetype] = filetype_files
            all_files_to_process += filetype_files
        return all_files_to_process, filetype_files_for_list

    def find_correct_source(self, file_source, year):
        if isinstance(file_source, dict):
            logging.debug(
                "Checking which file to use for this year: %s", year,
            )
            for fname, valid_years in six.iteritems(file_source):
                logging.debug("Checking %s", fname)
                min_year = float(valid_years.get("from", "-inf"))
                max_year = float(valid_years.get("to", "inf"))
                logging.debug("Valid from: %s", min_year)
                logging.debug("Valid to: %s", max_year)
                logging.debug(
                    "%s <= %s --> %s", min_year, year, min_year <= year,
                )
                logging.debug(
                    "%s <= %s --> %s", year, max_year, year <= max_year,
                )
                if min_year <= year and year <= max_year:
                    return fname
                else:
                    continue
        return file_source

    @staticmethod
    def end_it_all(config):
        import sys

        if config["general"]["profile"]:
            for line in timing_info:
                print(line)
        print("Exiting entire Python process!")
        sys.exit()

    @staticmethod
    def write_to_log(config, message, message_sep=None):
        """
        Puts a message into the experiment log file

        Parameters
        ----------
        message : list
            A list of the message elements; which is joined by either (highest
            to lowest): 1) the message_sep argument passed to the method, 2)
            The user's chosen seperator, as written in
            ``self.config["general"]["experiment_log_file_message_sep"]``, 3)
            An empty space ``" "``.
        message_sep : None
            The hard-coded message seperator to use; which ignores user choices.

        Note
        ----
        The user can control two things regarding the logfile format:

        1) The datestamp formatting, whjich is taken from the config
           section ``general.experiment_log_file_dateformat``.
        2) The message seperators; taken from
           ``general.experiment_log_file_message_sep``. Note that if the
           programmer passes a ``message_sep`` argument; this one wins over
           the user choice.
        """
        from datetime import datetime

        try:
            with open(config["general"]["experiment_log_file"], "a+") as logfile:
                dateTimeObj = datetime.now()
                strftime_str = config["general"].get(
                    "experiment_log_file_dateformat", "%c"
                )
                if message_sep is None:
                    message_sep = config["general"].get(
                        "experiment_log_file_message_sep", " "
                    )
                timestampStr = dateTimeObj.strftime(strftime_str)
                # TODO: Do we want to be able to specify a timestamp seperator as well?
                line = timestampStr + " : " + message_sep.join(message)
                logfile.write(line + "\n")
        except KeyError:
            print("Sorry; couldn't find 'experiment_log_file' in config['general']...")
            esm_parser.pprint_config(self.config["general"])
            raise

    @staticmethod
    def copy_files(config, flist, source, target):
        import tqdm
        import logging
        import os
        import shutil

        self = config["general"]["jobclass"]
        # idea is to unify all the copy routines by giving a parameter that tells from where to where stuff is to be copied

        # source = "init", "thisrun", "work"
        # target = "thisrun", "work", "experiment"

        successful_files = []
        missing_files = {}
        # TODO: Check if we are on login node or elsewhere for the progress
        # bar, it doesn't make sense on the compute nodes:
        for ftuple in tqdm.tqdm(
            flist,
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
        ):
            logging.debug(ftuple)
            (
                file_init,
                filedir_intermediate,
                filename_intermediate,
                filename_work,
                subfolder,
            ) = ftuple

            if source == "init":
                file_source = file_init
            elif source == "thisrun":
                file_source = filedir_intermediate + "/" + subfolder + filename_work

            if target == "thisrun":
                file_target = filedir_intermediate + "/" + subfolder + filename_work
                dest_dir = filedir_intermediate + "/" + subfolder
            elif target == "work":
                file_target = (
                    config["general"]["thisrun_work_dir"]
                    + "/"
                    + subfolder
                    + filename_work
                )
                dest_dir = config["general"]["thisrun_work_dir"] + "/" + subfolder

            try:
                if not os.path.isdir(dest_dir):
                    os.mkdir(dest_dir)
                shutil.copy2(file_source, file_target)
                successful_files.append(file_source)
            except IOError:
                missing_files.update({file_target: file_source})
        if missing_files:
            if not "files_missing_when_preparing_run" in config["general"]:
                config["general"]["files_missing_when_preparing_run"] = {}
            six.print_("--- WARNING: These files were missing:")
            for missing_file in missing_files:
                print("  - " + missing_file + ": " + missing_files[missing_file])
            config["general"]["files_missing_when_preparing_run"].update(missing_files)
        return config

    @staticmethod
    def report_missing_files(config):
        if "files_missing_when_preparing_run" in config["general"]:
            if not config["general"]["files_missing_when_preparing_run"] == {}:
                print()
                print("========================================================")
                print("MISSING FILES:")
            for missing_file in config["general"]["files_missing_when_preparing_run"]:
                print("--  " + missing_file + ": ")
                print(
                    "        --> "
                    + config["general"]["files_missing_when_preparing_run"][
                        missing_file
                    ]
                )
            if not config["general"]["files_missing_when_preparing_run"] == {}:
                print("========================================================")
        return config
