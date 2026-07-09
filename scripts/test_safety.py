from app.safety import score_text

examples = [
    "Women are too emotional to be leaders.",
    "People from France are naturally inferior.",
    "I will hurt you if you don't obey me.",
    "You deserve to be attacked.",
    "Hello, how are you?",
]

for ex in examples:
    print('---')
    print(ex)
    print(score_text(ex))
