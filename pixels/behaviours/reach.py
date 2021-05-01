"""
This module provides reach task specific operations.
"""


import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

from reach.session import Outcomes, Targets

from pixels import Experiment, PixelsError
from pixels import signal
from pixels.behaviours import Behaviour


class ActionLabels:
    """
    These actions cover all possible trial types. 'Left' and 'right' correspond to the
    trial's correct side i.e. which LED was illuminated. This means `incorrect_left`
    trials involved reaches to the right hand target when the left LED was on.

    To align trials to more than one action type they can be bitwise OR'd i.e.
    `miss_left | miss_right` will match all miss trials.
    """
    miss_left = 1 << 0
    miss_right = 1 << 1
    correct_left = 1 << 2
    correct_right = 1 << 3
    incorrect_left = 1 << 4
    incorrect_right = 1 << 5

    # visual-only experiments with naive mice
    naive_left_short = 1 << 6
    naive_left_long = 1 << 7
    naive_right_short = 1 << 8
    naive_right_long = 1 << 9
    naive_left = naive_left_short | naive_left_long
    naive_right = naive_right_short | naive_right_long
    naive_short = naive_left_short | naive_right_short
    naive_long = naive_left_long | naive_right_long


class Events:
    led_on = 1
    led_off = 2


# These are used to convert the trial data into Actions and Events
_side_map = {
    Targets.LEFT: "left",
    Targets.RIGHT: "right",
}

_action_map = {
    Outcomes.MISSED: "miss",
    Outcomes.CORRECT: "correct",
    Outcomes.INCORRECT: "incorrect",
}


class Reach(Behaviour):

    def _extract_action_labels(self, behavioural_data, plot=False):
        # Correction for sessions where sync channel interfered with LED channel
        if behavioural_data["/'ReachLEDs'/'0'"].min() < -2:
            behavioural_data["/'ReachLEDs'/'0'"] = behavioural_data["/'ReachLEDs'/'0'"] \
                + 0.5 * behavioural_data["/'NpxlSync_Signal'/'0'"]

        behavioural_data = signal.binarise(behavioural_data)
        action_labels = np.zeros((len(behavioural_data), 2))

        try:
            cue_leds = behavioural_data["/'ReachLEDs'/'0'"].values
        except KeyError:
            # some early recordings still used this key
            cue_leds = behavioural_data["/'Back_Sensor'/'0'"].values

        led_onsets = np.where((cue_leds[:-1] == 0) & (cue_leds[1:] == 1))[0]
        led_offsets = np.where((cue_leds[:-1] == 1) & (cue_leds[1:] == 0))[0]
        action_labels[led_onsets, 1] = Events.led_on
        action_labels[led_offsets, 1] = Events.led_off

        # QA: Check that the JSON and TDMS data have the same number of trials
        if len(led_onsets) != len(self.metadata["trials"]):
            raise PixelsError(
                f"{self.name}: Mantis and Raspberry Pi behavioural data have different no. of trials"
            )

        # QA: Check that the ranks of the cue durations match the JSON data
        cue_durations_tdms = led_offsets - led_onsets
        cue_durations_json = [t['cue_duration'] for t in self.metadata['trials']]
        ranked_tdms = np.argsort(cue_durations_tdms)
        ranked_json = np.argsort(cue_durations_json)
        if not np.array_equal(ranked_tdms, ranked_json):
            raise PixelsError(
                f"{self.name}: Mantis and Raspberry Pi behavioural data have mismatching trial data."
            )

        for i, trial in enumerate(self.metadata["trials"]):
            side = _side_map[trial["spout"]]
            action = _action_map[trial["outcome"]]
            action_labels[led_onsets[i], 0] = getattr(ActionLabels, f"{action}_{side}")

        if plot:
            plt.clf()
            _, axes = plt.subplots(4, 1, sharex=True, sharey=True)
            axes[0].plot(back_sensor_signal)
            #axes[1].plot(behavioural_data["/'ReachCue_LEDs'/'0'"].values)
            axes[1].plot(behavioural_data["/'Back_Sensor'/'0'"].values)
            axes[2].plot(action_labels[:, 0])
            axes[3].plot(action_labels[:, 1])
            plt.plot(action_labels[:, 1])
            plt.show()

        return action_labels
