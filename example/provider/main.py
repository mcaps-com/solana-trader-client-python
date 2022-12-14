import asyncio
import base64
import os

from solana.blockhash import Blockhash

import bxsolana
from bxsolana import provider, transaction
from bxsolana_trader_proto import api as proto

API_ENV = os.environ.get("API_ENV", "testnet")
if API_ENV not in ["mainnet", "testnet", "local"]:
    raise EnvironmentError(
        f'invalid API_ENV value: {API_ENV} (valid values: "mainnet", "testnet",'
        ' "local)'
    )

# trades stream is infrequent in terms of updates
RUN_SLOW_STREAMS = os.environ.get("RUN_SLOW_STREAMS", "true")
if RUN_SLOW_STREAMS == "false":
    RUN_SLOW_STREAMS = False
else:
    RUN_SLOW_STREAMS = True

RUN_TRADES = os.environ.get("RUN_TRADES", "true")
if RUN_TRADES == "false":
    RUN_TRADES = False
else:
    RUN_TRADES = True

# sample public key for trades API
PUBLIC_KEY = "4JCZomAb4eKcJQ9fqoi2JPT1TzjbhJEk8V8MmFKUQfnV"
USDC_WALLET = "8w1igsiZfsWnMTJSKkSvDQYYCZyf6aXMihuXEYpxcZVD"
OPEN_ORDERS = "4JCZomAb4eKcJQ9fqoi2JPT1TzjbhJEk8V8MmFKUQfnV"
SOL_USDC_MARKET = "9wFFyRfZBsuAha4YcuxcXLKwMxJR43S7fPfQLusDBzvT"
ORDER_ID = "3929156487700134707538850"


async def main():
    await ws()
    await http()
    await grpc()


async def http():
    # private keys are loaded from environment variable `PRIVATE_KEY` by default
    # alternatively, can specify the key manually in base58 str if loaded from other source
    # p = provider.HttpProvider("127.0.0.1", 9000, private_key="...")

    if API_ENV == "mainnet":
        p = provider.http()
    elif API_ENV == "local":
        p = provider.http_local()
    else:
        p = provider.http_testnet()
    api = await bxsolana.trader_api(p)

    # either `try`/`finally` or `async with` work with each type of provider
    try:
        await do_requests(api)
        await do_transaction_requests(api)
    except Exception as e:
        print(e)
        raise e
    finally:
        await p.close()


async def ws():
    if API_ENV == "mainnet":
        p = provider.ws()
    elif API_ENV == "local":
        p = provider.ws_local()
    else:
        p = provider.ws_testnet()

    async with p as api:
        await do_requests(api)
        await do_transaction_requests(api)
        await do_stream(api)


async def grpc():
    if API_ENV == "mainnet":
        p = provider.grpc()
    elif API_ENV == "local":
        p = provider.grpc_local()
    else:
        p = provider.grpc_testnet()
    api = await bxsolana.trader_api(p)

    try:
        await do_requests(api)
        await do_transaction_requests(api)
        await do_stream(api)
    finally:
        await p.close()


async def do_requests(api: bxsolana.Provider):

    print("getting price")
    print((await api.get_price(tokens=[
            "So11111111111111111111111111111111111111112", "USDC", "SOL", "USDT"
        ])).to_json())

    print("getting pools")
    print((await api.get_pools(projects=[proto.Project.P_RAYDIUM])).to_json())

    print("getting quotes")
    print((await api.get_quotes(in_token="USDC", out_token= "SOL",
                         in_amount = 0.01, slippage= 10 , limit = 1, projects=[proto.Project.P_RAYDIUM])).to_json())

    print("posting route swap")
    step = proto.RouteStep()
    step.in_token = "USDC"
    step.in_amount = 0.01
    step.out_token = "SOL"
    step.out_amount = 0.01
    step.out_amount_min = 0.01
    step_project = proto.StepProject()
    step_project.label = "Raydium"
    step_project.id = "1234"
    step.project = step_project
    print((await api.post_route_trade_swap(project=proto.Project.P_RAYDIUM,
                                           owner_address=PUBLIC_KEY, steps=[step])).to_json())


    # markets API
    print("fetching all markets")
    print((await api.get_markets()).to_json())

    print("fetching SOL/USDC orderbook")
    print((await api.get_orderbook(market="SOLUSDC", project=proto.Project.P_OPENBOOK)).to_json())

    print("fetching SOL/USDC ticker")
    print((await api.get_tickers(market="SOLUSDC", project=proto.Project.P_OPENBOOK)).to_json())

    print("fetching all tickers")
    print((await api.get_tickers(project=proto.Project.P_OPENBOOK)).to_json())

    # trade API
    print("fetching open orders for account")
    print(
        (
            await api.get_open_orders(market="SOLUSDC", address=PUBLIC_KEY, project=proto.Project.P_OPENBOOK)
        ).to_json()
    )

    print("fetching unsettled amounts")
    print(
        (
            await api.get_unsettled(market="SOLUSDC", owner_address=PUBLIC_KEY, project=proto.Project.P_OPENBOOK)
        ).to_json()
    )

    print("fetching account balance amounts")
    print((await api.get_account_balance(owner_address=PUBLIC_KEY)).to_json())

    print(
        "generating unsigned order (no sign or submission) to sell 0.1 SOL for"
        " USDC at 150_000 USD/SOL"
    )
    print(
        (
            await api.post_order(
                owner_address=PUBLIC_KEY,
                payer_address=PUBLIC_KEY,
                market="SOLUSDC",
                side=proto.Side.S_ASK,
                type=[proto.OrderType.OT_LIMIT],
                amount=0.1,
                price=150_000,
                project=proto.Project.P_OPENBOOK,
                # optional, but much faster if known
                open_orders_address=OPEN_ORDERS,
                # optional, for identification
                client_order_i_d=0,
            )
        ).to_json()
    )

    print("generate cancel order")
    print(
        (
            await api.post_cancel_order(
                order_i_d=ORDER_ID,
                side=proto.Side.S_ASK,
                market_address="SOLUSDC",
                project=proto.Project.P_OPENBOOK,
                owner_address=PUBLIC_KEY,
                open_orders_address=OPEN_ORDERS,
            )
        ).to_json()
    )

    print("generate cancel order by client ID")
    print(
        await api.post_cancel_by_client_order_i_d(
            client_order_i_d=123,
            market_address=SOL_USDC_MARKET,
            owner_address=PUBLIC_KEY,
            project=proto.Project.P_OPENBOOK,
            open_orders_address=OPEN_ORDERS,
        )
    )

    print("generate settle order")
    print(
        await api.post_settle(
            owner_address=PUBLIC_KEY,
            market="SOLUSDC",
            base_token_wallet=PUBLIC_KEY,
            quote_token_wallet=USDC_WALLET,
            project=proto.Project.P_OPENBOOK,
            open_orders_address=OPEN_ORDERS,
        )
    )

    print(
        (
            await api.post_replace_by_client_order_i_d(
                owner_address=PUBLIC_KEY,
                payer_address=PUBLIC_KEY,
                market="SOLUSDC",
                side=proto.Side.S_ASK,
                type=[proto.OrderType.OT_LIMIT],
                amount=0.1,
                price=150_000,
                project=proto.Project.P_OPENBOOK,
                # optional, but much faster if known
                open_orders_address=OPEN_ORDERS,
                # optional, for identification
                client_order_i_d=123,
            )
        ).to_json()
    )

    print(
        (
            await api.post_replace_order(
                owner_address=PUBLIC_KEY,
                payer_address=PUBLIC_KEY,
                market="SOLUSDC",
                side=proto.Side.S_ASK,
                type=[proto.OrderType.OT_LIMIT],
                amount=0.1,
                price=150_000,
                project=proto.Project.P_OPENBOOK,
                # optional, but much faster if known
                open_orders_address=OPEN_ORDERS,
                # optional, for identification
                client_order_i_d=0,
                order_i_d=ORDER_ID,
            )
        ).to_json()
    )


async def create_transaction_with_memo(api: bxsolana.Provider):
    private_key = transaction.load_private_key_from_env()

    instruction = transaction.create_trader_api_memo_instruction("hi from dev")

    recent_block_hash_resp = await api.get_recent_block_hash()
    recent_block_hash = Blockhash(recent_block_hash_resp.block_hash)
    instructions = [instruction]

    tx_serialized = transaction.build_fully_signed_txn(
        recent_block_hash, private_key.public_key, instructions, private_key
    )
    single_memo_txn = base64.b64encode(tx_serialized).decode("utf-8")
    print("serialized memo single_memo_txn", single_memo_txn)

    post_submit_response = await api.post_submit(
        transaction=proto.TransactionMessage(single_memo_txn),
        skip_pre_flight=True,
    )
    print("signature for single memo txn", post_submit_response.signature)

    double_memo_txn_signed = transaction.add_memo_to_serialized_txn(
        single_memo_txn, "hi from dev2", private_key.public_key, private_key
    )
    print("double_memo_txn_signed", double_memo_txn_signed)
    post_submit_response = await api.post_submit(
        transaction=proto.TransactionMessage(double_memo_txn_signed),
        skip_pre_flight=True,
    )
    print("signature for double memo tx", post_submit_response.signature)


async def do_transaction_requests(api: bxsolana.Provider):
    if not RUN_TRADES:
        print("skipping transaction requests: set by environment")
        return

    print("creating transactions with memo")
    await create_transaction_with_memo(api)

    print(
        "submitting order (generate + sign) to sell 0.1 SOL for USDC at 150_000"
        " USD/SOL"
    )
    print(
        await api.submit_order(
            owner_address=PUBLIC_KEY,
            payer_address=PUBLIC_KEY,
            market="SOLUSDC",
            side=proto.Side.S_ASK,
            types=[proto.OrderType.OT_LIMIT],
            amount=0.1,
            price=150_000,
            project=proto.Project.P_OPENBOOK,
            # optional, but much faster if known
            open_orders_address=OPEN_ORDERS,
            # optional, for identification
            client_order_id=0,
        )
    )

    print("submit cancel order")
    print(
        await api.submit_cancel_order(
            order_i_d=ORDER_ID,
            side=proto.Side.S_ASK,
            market_address="SOLUSDC",
            owner_address=PUBLIC_KEY,
            project=proto.Project.P_OPENBOOK,
            open_orders_address=OPEN_ORDERS,
        )
    )

    print("submit cancel order by client ID")
    print(
        await api.submit_cancel_by_client_order_i_d(
            client_order_i_d=123,
            market_address=SOL_USDC_MARKET,
            owner_address=PUBLIC_KEY,
            project=proto.Project.P_OPENBOOK,
            open_orders_address=OPEN_ORDERS,
        )
    )
    print("submit settle order")
    print(
        await api.submit_settle(
            owner_address=PUBLIC_KEY,
            market="SOLUSDC",
            base_token_wallet=PUBLIC_KEY,
            quote_token_wallet=USDC_WALLET,
            project=proto.Project.P_OPENBOOK,
            open_orders_address="",  # optional
        )
    )

    print(
        "submitting order (generate + sign) to sell 0.1 SOL for USDC at 150_000"
        " USD/SOL"
    )
    print(
        await api.submit_replace_by_client_order_i_d(
            owner_address=PUBLIC_KEY,
            payer_address=PUBLIC_KEY,
            market="SOLUSDC",
            side=proto.Side.S_ASK,
            types=[proto.OrderType.OT_LIMIT],
            amount=0.1,
            price=150_000,
            project=proto.Project.P_OPENBOOK,
            # optional, but much faster if known
            open_orders_address=OPEN_ORDERS,
            # optional, for identification
            client_order_i_d=123,
        )
    )
    print(
        "submitting order (generate + sign) to sell 0.1 SOL for USDC at 150_000"
        " USD/SOL"
    )
    print(
        await api.submit_replace_order(
            owner_address=PUBLIC_KEY,
            payer_address=PUBLIC_KEY,
            market="SOLUSDC",
            side=proto.Side.S_ASK,
            types=[proto.OrderType.OT_LIMIT],
            amount=0.1,
            price=150_000,
            project=proto.Project.P_OPENBOOK,
            # optional, but much faster if known
            open_orders_address=OPEN_ORDERS,
            # optional, for identification
            client_order_id=0,
            order_i_d=ORDER_ID,
        )
    )


# websockets / GRPC only
async def do_stream(api: bxsolana.Provider):
    item_count = 0

    if RUN_SLOW_STREAMS:
        print("streaming orderbook updates...")
        async for response in api.get_orderbooks_stream(markets=["SOLUSDC"], project=proto.Project.P_OPENBOOK):
            print(response.to_json())
            item_count += 1
            if item_count == 5:
                item_count = 0
                break

    if RUN_SLOW_STREAMS:
        print("streaming ticker updates...")
        async for response in api.get_tickers_stream(market="SOLUSDC", project=proto.Project.P_OPENBOOK):
            print(response.to_json())
            item_count += 1
            if item_count == 5:
                item_count = 0
                break

    if RUN_SLOW_STREAMS:
        print("streaming trade updates...")
        async for response in api.get_trades_stream(market="SOLUSDC", project=proto.Project.P_OPENBOOK):
            print(response.to_json())
            item_count += 1
            if item_count == 1:
                item_count = 0
                break

    if RUN_SLOW_STREAMS:
        print("streaming pool reserves...")
        async for response in api.get_pool_reserves_stream(projects=[proto.Project.P_RAYDIUM]):
            print(response.to_json())
            item_count += 1
            if item_count == 1:
                item_count = 0
                break

    if RUN_SLOW_STREAMS:
        print("streaming price streams...")
        async for response in api.get_prices_stream(projects=[proto.Project.P_RAYDIUM], tokens=[
            "So11111111111111111111111111111111111111112", "USDC", "SOL", "USDT"
        ]):
            print(response.to_json())
            item_count += 1
            if item_count == 1:
                item_count = 0
                break


if __name__ == "__main__":
    asyncio.run(main())
