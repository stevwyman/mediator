from django.test import TestCase, Client

class Working_Mediation(TestCase):
    own_id = None
    share_id = None

    def check_own_id_data_missing(self) -> None:
        client = Client(enforce_csrf_checks=False)
        response = client.get(
            "/mediate/check/" + str(self.own_id),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context["result"])
        self.assertEqual(response.context["result"]["text"], "ask value still missing")

    def check_own_id_data_complete(self) -> None:
        client = Client(enforce_csrf_checks=False)
        response = client.get(
            "/mediate/check/" + str(self.own_id),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context["result"])
        self.assertEqual(response.context["result"]["text"], "negotiation is possible")

    def update_other_side(self) -> None:
        client = Client(enforce_csrf_checks=False)
        response = client.get(
            "/mediate/check/" + str(self.share_id),
        )
        self.assertEqual(response.status_code, 200)

        response = client.post(
            "/mediate/process",
            data={"id": self.share_id, "type": "Ask", "provided_value": 100},
            follow=True
        )

        self.assertRedirects(
            response,
            "/mediate/check/" + str(self.share_id),
            status_code=302,
            target_status_code=200,
            fetch_redirect_response=True,
        )

        self.assertIsNotNone(response.context["result"])

        # as Ask is 100 and bis is 110, negotiation is possible
        self.assertEqual(response.context["result"]["text"], "negotiation is possible")

    def check_other_side(self) -> None:

        client = Client(enforce_csrf_checks=False)
        response = client.get(
            "/mediate/check/" + str(self.own_id),
        )
        self.assertEqual(response.status_code, 200)

    def setUp(self) -> None:
        """
        bid 110: I would buy for up to 110, hence I would pay max 100
        """
        client = Client(enforce_csrf_checks=False)
        response = client.post(
            "/mediate/start",
            data={
                "type": "Bid",
                "provided_value": 110,
                "duration_input": 2,
                "duration_display": 2,
            },
        )
        self.assertEqual(response.status_code, 200)

        self.own_id = response.context["return_data"]["own_id"]
        self.share_id = response.context["return_data"]["share_id"]

        self.assertIsNotNone(self.own_id)
        self.assertIsNotNone(self.share_id)

    def test_mediation(self) -> None:
        self.check_own_id_data_missing()
        self.update_other_side()
        self.check_own_id_data_complete()
        self.check_other_side()
        self.check_other_side()
        self.check_own_id_data_complete()


class Not_Working_Mediation(TestCase):
    own_id = None
    share_id = None

    def setUp(self) -> None:
        """
        bid 100: I would buy for up to 100, hence I would pay max 100
        """
        client = Client(enforce_csrf_checks=False)
        response = client.post(
            "/mediate/start",
            data={
                "type": "Bid",
                "provided_value": 100,
                "duration_input": 2,
                "duration_display": 2,
            },
        )
        self.assertEqual(response.status_code, 200)

        self.own_id = response.context["return_data"]["own_id"]
        self.share_id = response.context["return_data"]["share_id"]

        self.assertIsNotNone(self.own_id)
        self.assertIsNotNone(self.share_id)

    def test_own_id(self) -> None:

        client = Client(enforce_csrf_checks=False)
        response = client.get(
            "/mediate/check/" + str(self.own_id),
        )
        self.assertEqual(response.status_code, 200)

    def test_shared(self) -> None:
        """
        Ask 110: Seller would sell for min 110
        """

        client = Client(enforce_csrf_checks=False)
        response = client.get(
            "/mediate/check/" + str(self.share_id),
        )
        self.assertEqual(response.status_code, 200)

        response = client.post(
            "/mediate/process",
            data={"id": self.share_id, "type": "Ask", "provided_value": 110},
            follow=True
        )

        self.assertRedirects(
            response,
            "/mediate/check/" + str(self.share_id),
            status_code=302,
            target_status_code=200,
            fetch_redirect_response=True,
        )

        self.assertIsNotNone(response.context["result"])

        # as Ask is 110 and bis is 100, no negotiation is possible
        self.assertEqual(response.context["result"]["text"], "negotiation is not possible")
