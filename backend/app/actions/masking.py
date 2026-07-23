def mask_value(value, entity_type):


    if entity_type == "RRN":

        # 090302-4565288
        # 090302-4*****

        return value[:8] + "*****"



    elif entity_type == "CARD":


        clean = value.replace(
            "-",
            ""
        ).replace(
            " ",
            ""
        )


        if len(clean) == 16:

            return (
                clean[:4]
                + "-****-****-"
                + clean[-4:]
            )


        return "****-****-****-****"



    elif entity_type == "BUSINESS_NUMBER":

        return "***-**-*****"



    elif entity_type == "PASSPORT":

        return "********"



    elif entity_type == "DRIVER_LICENSE":

        return "********"



    elif entity_type == "FOREIGNER_REGISTRATION":

        return "********"



    else:

        return "*" * len(value)