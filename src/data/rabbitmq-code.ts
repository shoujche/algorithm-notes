import publishClient from '../code/component/rabbitmq/publish_client.py?raw';
import exchangeRoute from '../code/component/rabbitmq/exchange_route.py?raw';
import confirmAck from '../code/component/rabbitmq/confirm_ack.py?raw';
import consumeClient from '../code/component/rabbitmq/consume_client.py?raw';
import idempotentConsumer from '../code/component/rabbitmq/idempotent_consumer.py?raw';

export const CODE_DIR = 'src/code/component/rabbitmq';

export { publishClient, exchangeRoute, confirmAck, consumeClient, idempotentConsumer };
