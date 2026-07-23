from app.actions.policy import POLICY
from app.actions.masking import mask_value


from app.replace.replace_phone import replace_phone
from app.replace.replace_email import replace_email
from app.replace.replace_bank_account import replace_account



def apply_policy(
    original_text,
    regex_entities,
    llm_entities
):


    entities = []



    # Regex Entity

    for entity in regex_entities:

        entities.append(
            {
                "type": entity["type"],
                "value": entity["value"],
                "start": entity["start"],
                "end": entity["end"],
                "source": "regex"
            }
        )



    # LLM Entity

    for entity_type, values in llm_entities.items():

        for item in values:

            entities.append(
                {
                    "type": entity_type,
                    "value": item["text"],
                    "start": item["start"],
                    "end": item["end"],
                    "source": "llm"
                }
            )



    # 정렬

    entities.sort(
        key=lambda x: (
            x["start"],
            -(x["end"] - x["start"])
        )
    )



    # 중복 제거

    filtered = []


    for entity in entities:

        overlap = False


        for saved in filtered:


            if (
                entity["start"] >= saved["start"]
                and entity["end"] <= saved["end"]
            ):

                overlap = True
                break



        if not overlap:

            filtered.append(entity)



    result = original_text



    # 뒤에서부터 처리

    filtered.sort(
        key=lambda x:x["start"],
        reverse=True
    )



    for entity in filtered:


        entity_type = entity["type"]

        value = entity["value"]


        action = POLICY.get(
            entity_type,
            "mask"
        )



        if action == "mask":


            new_value = mask_value(
                value,
                entity_type
            )



        elif action == "replace":


            if entity_type == "PHONE":

                new_value = replace_phone(value)



            elif entity_type == "EMAIL":

                new_value = replace_email(value)



            elif entity_type == "BANK_ACCOUNT":

                new_value = replace_account(value)



            elif entity_type == "PERSON":

                new_value = "[사용자 이름]"



            elif entity_type == "ADDRESS":

                new_value = "[주소]"



            elif entity_type == "ORGANIZATION":

                new_value = "[기관]"



            else:

                new_value = "[REDACTED]"



        else:

            new_value = value



        result = (
            result[:entity["start"]]
            + new_value
            + result[entity["end"]:]
        )



    return result