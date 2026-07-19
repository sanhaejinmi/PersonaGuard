def mask_text(text, entities):

    masked = text

    targets = []

    for category in ["PERSON", "ADDRESS", "ORGANIZATION"]:

        for item in entities.get(category, []):

            targets.append(
                (
                    item["text"],
                    category
                )
            )

    targets.sort(
        key=lambda x: len(x[0]),
        reverse=True
    )

    for value, category in targets:

        masked = masked.replace(
            value,
            f"[{category}]"
        )

    return masked