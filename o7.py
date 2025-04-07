import pprint
from agentforge.cog import Cog


def main():
    cogarch = Cog('o7')
    print("o7 is awaiting your input...")
    while True:
        user_input: str = input("You: ")
        if user_input.lower() == 'quit':
            print("Chao!")
            break

        output = cogarch.run(question=user_input)
        flow = cogarch.get_track_flow_trail()
        print(f"---------")
        # pprint.pprint(flow)
        print(flow)
        print(f"---------")
        print(output)
        print(f"---------")

if __name__ == "__main__":
    main()