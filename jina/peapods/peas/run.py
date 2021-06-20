import os

from ...enums import RuntimeBackendType
from ...excepts import RuntimeFailToStart, RuntimeTerminated
from ..runtimes.jinad import JinadRuntime

__all__ = ['run']


def run(
    args,
    logger,
    envs,
    runtime_cls,
    local_runtime_ctrl_addr,
    zed_runtime_ctrl_addres,
    is_ready_event,
    is_shutdown_event,
):
    """Method representing the :class:`BaseRuntime` activity.

    This method is the main method of the process started by a `Pea`

    .. note::
        :meth:`run` is running in subprocess/thread, the exception can not be propagated to the main process.
        Hence, please do not raise any exception here.
    """

    def _build_runtime():
        # This is due to the fact that JinadRuntime instantiates a Zmq server at local_ctrl_addr that will itself
        # send ctrl command
        # (TODO: Joan) Fix that in _wait_for_cancel from async runtime
        ctrl_addr = (
            local_runtime_ctrl_addr
            if runtime_cls == JinadRuntime
            else zed_runtime_ctrl_addres
        )
        return runtime_cls(args, ctrl_addr=ctrl_addr)

    def _set_envs():
        if args.env:
            if args.runtime_backend == RuntimeBackendType.THREAD:
                logger.warning(
                    'environment variables should not be set when runtime="thread".'
                )
            else:
                os.environ.update({k: str(v) for k, v in envs.items()})

    def _unset_envs():
        if envs and args.runtime_backend != RuntimeBackendType.THREAD:
            for k in envs.keys():
                os.unsetenv(k)

    try:
        _set_envs()
        runtime = _build_runtime()
    except Exception as ex:
        logger.error(
            f'{ex!r} during {runtime_cls!r} initialization'
            + f'\n add "--quiet-error" to suppress the exception details'
            if not args.quiet_error
            else '',
            exc_info=not args.quiet_error,
        )
    else:
        is_ready_event.set()
        try:
            runtime.run_forever()
        except RuntimeFailToStart as ex:
            logger.error(
                f'{ex!r} during {runtime_cls.__init__!r}'
                + f'\n add "--quiet-error" to suppress the exception details'
                if not args.quiet_error
                else '',
                exc_info=not args.quiet_error,
            )
        except RuntimeTerminated:
            logger.info(f'{runtime!r} is end')
        except KeyboardInterrupt:
            logger.info(f'{runtime!r} is interrupted by user')
        except (Exception, SystemError) as ex:
            logger.error(
                f'{ex!r} during {runtime.run_forever!r}'
                + f'\n add "--quiet-error" to suppress the exception details'
                if not args.quiet_error
                else '',
                exc_info=not args.quiet_error,
            )

        try:
            runtime.teardown()
        except Exception as ex:
            logger.error(
                f'{ex!r} during {runtime.teardown!r}'
                + f'\n add "--quiet-error" to suppress the exception details'
                if not args.quiet_error
                else '',
                exc_info=not args.quiet_error,
            )
    finally:
        is_shutdown_event.set()
        is_ready_event.clear()
        _unset_envs()
