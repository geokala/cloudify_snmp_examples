import time

import jinja2
from cloudify.exceptions import NonRecoverableError
from cloudify.decorators import operation
from cloudify.manager import get_rest_client


NODE_PROPERTY_BASE = 'managed_monitoring'
REQUIRED_PARAMS = (
    'deployment_name',
    'node_name',
    'add_operation_name',
    'remove_operation_name',
)


def required_params_supplied(params, ctx):
    healthy = True
    for required in REQUIRED_PARAMS:
        if required not in params:
            ctx.logger.warn(
                'Missing required parameter from node properties: '
                'properties.{base}.{param}'.format(
                    base=NODE_PROPERTY_BASE,
                    param=required,
                )
            )
            healthy = False
    return healthy


@operation
def add_monitoring(ctx):
    _process_monitoring_request(
        add_or_remove='add',
        starting_message=(
            'Adding monitoring to node {node} of deployment {dep}, using '
            'operation {op}'
        ),
        success_message='Successfully added monitoring',
        failure_message=(
            'Failed adding monitoring, execution {id} did not succeed with '
            'status: {state}'
        ),
        ctx=ctx,
    )


@operation
def remove_monitoring(ctx):
    _process_monitoring_request(
        add_or_remove='remove',
        starting_message=(
            'Adding monitoring to node {node} of deployment {dep}, using '
            'operation {op}'
        ),
        success_message='Successfully added monitoring',
        failure_message=(
            'Failed adding monitoring, execution {id} did not succeed with '
            'status: {state}'
        ),
        ctx=ctx,
    )


def _process_monitoring_request(add_or_remove,
                                starting_message,
                                success_message,
                                failure_message,
                                ctx):
    monitoring_details = ctx.node.properties.get(NODE_PROPERTY_BASE, {})
    operation_getter = '{0}_operation_name'.format(add_or_remove)
    inputs_getter = '{0}_operation_inputs'.format(add_or_remove)

    if not required_params_supplied(monitoring_details, ctx):
        raise NonRecoverableError(
            'Required monitoring parameters not supplied, no monitoring will '
            'be configured.'
        )

    # We're loading this here rather than using DSL operations because DSL
    # operations aren't very helpful when trying to work with a specific
    # node instance.
    # This method means that inputs can be specified that refer to the node
    # instance that is currently being deployed (e.g. when scaling or
    # otherwise deploying more than one instance).
    operation_inputs = jinja2.Template(
        monitoring_details.get(inputs_getter, '{}')
    )
    operation_inputs.render(ctx=ctx)

    ctx.logger.info(
        starting_message.format(
            node=monitoring_details['node_name'],
            dep=monitoring_details['deployment_name'],
            op=monitoring_details[operation_getter],
        )
    )

    client = get_rest_client()
    execution = client.executions.start(
        deployment_id=monitoring_details['deployment_name'],
        workflow_id='execute_operation',
        parameters={
            'node_ids': monitoring_details['node_name'],
            'operation': monitoring_details[operation_getter],
            'operation_kwargs': operation_inputs,
            'allow_kwargs_override': True,
        },
    )

    while execution.status not in execution.END_STATES:
        ctx.logger.info(
            'Waiting for execution {id}. '
            'Current state: {state}'.format(
                id=execution.id,
                state=execution.status_display,
            )
        )
        time.sleep(3)
        execution = client.executions.get(
            execution_id=execution.id,
        )

    if execution.status == execution.TERMINATED:
        ctx.logger.info(success_message)
    else:
        raise NonRecoverableError(
            failure_message.format(
                id=execution.id,
                state=execution.status_display,
            )
        )
