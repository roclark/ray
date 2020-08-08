from abc import abstractmethod, ABCMeta
import logging
from typing import Dict, Optional

from ray.rllib.evaluation.episode import MultiAgentEpisode
from ray.rllib.models.modelv2 import ModelV2
from ray.rllib.utils.types import AgentID, EpisodeID, PolicyID, \
    TensorType

logger = logging.getLogger(__name__)


class _SampleCollector(metaclass=ABCMeta):
    """Collects samples for all policies and agents from a multi-agent env.

    Note: This is an experimental class only used when
    `config._use_trajectory_view_api` = True.
    Once `_use_trajectory_view_api` becomes the default in configs:
    This class will deprecate the `SampleBatchBuilder` and
    `MultiAgentBatchBuilder` classes.

    This API is controlled by RolloutWorker objects to store all data
    generated by Environments and Policies/Models during rollout and
    postprocessing. It's purposes are to a) make data collection and
    SampleBatch/input_dict generation from this data faster, b) to unify
    the way we collect samples from environments and model (outputs), thereby
    allowing for possible user customizations, c) to allow for more complex
    inputs fed into different policies (e.g. multi-agent case with inter-agent
    communication channel).
    """

    @abstractmethod
    def add_init_obs(self, episode_id: EpisodeID, agent_id: AgentID,
                     policy_id: PolicyID, init_obs: TensorType) -> None:
        """Adds an initial obs (after reset) to this collector.

        Since the very first observation in an environment is collected w/o
        additional data (w/o actions, w/o reward) after env.reset() is called,
        this method initializes a new trajectory for a given agent.
        `add_init_obs()` has to be called first for each agent/episode-ID
        combination. After this, only `add_action_reward_next_obs()` must be
        called for that same agent/episode-pair.

        Args:
            episode_id (EpisodeID): Unique id for the episode we are adding
                values for.
            agent_id (AgentID): Unique id for the agent we are adding
                values for.
            policy_id (PolicyID): Unique id for policy controlling the agent.
            init_obs (TensorType): Initial observation (after env.reset()).

        Examples:
            >>> obs = env.reset()
            >>> collector.add_init_obs(12345, 0, "pol0", obs)
            >>> obs, r, done, info = env.step(action)
            >>> collector.add_action_reward_next_obs(12345, 0, "pol0", {
            ...     "action": action, "obs": obs, "reward": r, "done": done
            ... })
        """
        raise NotImplementedError

    @abstractmethod
    def add_action_reward_next_obs(self, episode_id: EpisodeID,
                                   agent_id: AgentID, policy_id: PolicyID,
                                   values: Dict[str, TensorType]) -> None:
        """Add the given dictionary (row) of values to this collector.

        The incoming data (`values`) must include action, reward, done, and
        next_obs information and may include any other information.
        For the initial observation (after Env.reset()) of the given agent/
        episode-ID combination, `add_initial_obs()` must be called instead.

        Args:
            episode_id (EpisodeID): Unique id for the episode we are adding
                values for.
            agent_id (AgentID): Unique id for the agent we are adding
                values for.
            policy_id (PolicyID): Unique id for policy controlling the agent.
            values (Dict[str, TensorType]): Row of values to add for this
                agent. This row must contain the keys SampleBatch.ACTION,
                REWARD, NEW_OBS, and DONE.

        Examples:
            >>> obs = env.reset()
            >>> collector.add_init_obs(12345, 0, "pol0", obs)
            >>> obs, r, done, info = env.step(action)
            >>> collector.add_action_reward_next_obs(12345, 0, "pol0", {
            ...     "action": action, "obs": obs, "reward": r, "done": done
            ... })
        """
        raise NotImplementedError

    @abstractmethod
    def total_env_steps(self) -> int:
        """Returns total number of steps taken in the env (sum of all agents).

        Returns:
            int: The number of steps taken in total in the environment over all
                agents.
        """
        raise NotImplementedError

    @abstractmethod
    def get_inference_input_dict(self, model: ModelV2) -> \
            Dict[str, TensorType]:
        """Returns input_dict for an inference forward pass from our data.

        The input_dict can then be used for action computations.

        Args:
            model (ModelV2): The ModelV2 object for which to generate the view
                (input_dict) from `data`.

        Returns:
            Dict[str, TensorType]: The input_dict to be passed into the ModelV2
                for inference/training.

        Examples:
            >>> obs, r, done, info = env.step(action)
            >>> collector.add_action_reward_next_obs(12345, 0, "pol0", {
            ...     "action": action, "obs": obs, "reward": r, "done": done
            ... })
            >>> input_dict = collector.get_inference_input_dict(policy.model)
            >>> action = policy.compute_actions_from_input_dict(input_dict)
            >>> # repeat
        """
        raise NotImplementedError

    @abstractmethod
    def has_non_postprocessed_data(self) -> bool:
        """Returns whether there is pending, unprocessed data.

        Returns:
            bool: True if there is at least some data that has not been
                postprocessed yet.
        """
        raise NotImplementedError

    @abstractmethod
    def postprocess_trajectories_so_far(
            self, episode: Optional[MultiAgentEpisode] = None) -> None:
        """Apply postprocessing to unprocessed data (in one or all episodes).

        Generates (single-trajectory) SampleBatches for all Policies/Agents and
        calls Policy.postprocess_trajectory on each of these. Postprocessing
        may happens in-place, meaning any changes to the viewed data columns
        are directly reflected inside this collector's buffers.
        Also makes sure that additional (newly created) data columns are
        correctly added to the buffers.

        Args:
            episode (Optional[MultiAgentEpisode]): The Episode object for which
                to post-process data. If not provided, postprocess data for all
                episodes.
        """
        raise NotImplementedError

    @abstractmethod
    def get_multi_agent_batch_and_reset(self):
        """Returns the accumulated sample batches for each policy.

        Any unprocessed rows will be first postprocessed with a policy
        postprocessor. The internal state of this builder will be reset.

        Args:
            episode (Optional[MultiAgentEpisode]): The Episode object that
                holds this MultiAgentBatchBuilder object or None.

        Returns:
            MultiAgentBatch: Returns the accumulated sample batches for each
                policy inside one MultiAgentBatch object.
        """
        raise NotImplementedError

    @abstractmethod
    def check_missing_dones(self, episode_id: EpisodeID) -> None:
        raise NotImplementedError