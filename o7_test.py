import pprint
from agentforge.cog import Cog


def main():
    # Instantiate the Cog using its YAML prompt file
    cogarch = Cog('o7')
    print("o7 is awaiting your input...")
    while True:
        user_input: str = input("You: ")
        if user_input.lower() == 'quit':
            print("Chao!")
            break

        output = cogarch.run(message=user_input)
        print(f"---------")
        pprint.pprint(output)
        print(f"---------")
        print(output['generate']['response'].get('final_response'))
        print(f"---------")

if __name__ == "__main__":
    main()