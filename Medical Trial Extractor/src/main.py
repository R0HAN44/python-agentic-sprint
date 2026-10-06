# from utils import extract_agent, save_extracted_data
import asyncio

# unstructured_medical_text = input("Enter the Clinical/Medical/Research texts from which structured data to be extracted:\n")

# result = extract_agent(unstructured_medical_text)

# if result is None:
#     print("Model returned nothing or refused")
# else:
#     save_extracted_data(result)
#     print("Extracted structured data:\n", result.model_dump_json(indent=2))


def numbers():
    try:
        yield 1
        yield 2
        received = yield
        print(received)
    finally:
        print("Generator Closed")

n = numbers()

gen_exp = (x * x for x in range(5))
# print(gen_exp)
# print(list(gen_exp))
# print(sum(gen_exp))
# total = sum(x*x for x in range(10))
# print(total)
# print(next(n))
# print(next(n))
# print(next(n))

# n.send("sending text")
n.close()

async def stream_events():
    yield "Event1"
    await asyncio.sleep(2)
    yield "Event2"
    await asyncio.sleep(2)
    yield "Event3"

async def process_event(event):
    async with semaphore:
        print(f"{event} started")
        await asyncio.sleep(2)
        print(f"{event} finsihed.")

semaphore = asyncio.Semaphore(10)

number_of_events = 100

async def main():
    tasks = [asyncio.create_task(process_event("Event " + str(event))) for event in range(number_of_events)]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())