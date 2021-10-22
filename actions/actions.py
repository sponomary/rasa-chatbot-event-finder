from datetime import datetime
from typing import Text, List, Any, Dict
from rasa_sdk import Tracker,  Action, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict
import dateutil.parser
import json
import http.client


# Classe de l'action en cas de demande de l'heure
class ActionGiveTime(Action):
    def name(self) -> Text:
        return "action_show_time"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(text=f"Nous sommes le {datetime.now():%d-%m-%Y} et il est {datetime.now():%H:%M} .")
        return []

# Classe du formulaire de saisie de la catégorie, du prix de la date d'un évènement
class ValidateEvenementForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_evenement_form"

    # Validation lors de la saisie de l'évènement (concert, spectacle, exposition, animation)
    def validate_evenement(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate 'evenement' value."""
        print(f"Nom de l'évènement renseigné : {slot_value}")
        if len(slot_value) <= 1:
            dispatcher.utter_message(text = f"Il est nécessaire de saisir quelque chose.")
            return {"evenement": None}
        else:
            return {"evenement": slot_value}

    # Validation lors de la saisie du prix de l'évènement
    def validate_prix(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate `prix` value."""
        print(f"Prix renseigné= {slot_value} ")
        if len(slot_value) <= 1:
            dispatcher.utter_message(text=f"Il est nécessaire de saisir quelque chose.")
            return {"prix": None}
        else:
            return {"prix": slot_value}

    # Validation lors de la saisie de la date de l'évènement
    def validate_date(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate `date` value."""
        print(f"Date renseignée= {slot_value} ")
        if len(slot_value) <= 1:
            dispatcher.utter_message(text=f"Il est nécessaire de saisir quelque chose.")
            return {"date": None}
        else:
            try:
                dateEven = datetime.strptime(tracker.get_slot("date"), "%d/%m/%Y")
                # Controle : la saisie d'une date dans le passé provoque un message d'erreur
                if dateEven.date() < datetime.now().date(): 
                    dispatcher.utter_message(text=f"Il faut saisir une date supérieur ou égale à aujourd'hui !")
                    return {"date": None}
                else :
                    return {"date": slot_value}
            except ValueError: # Exception si la date saisie n'est pas une date valide (par exemple 45/23/2040)
                dispatcher.utter_message(text=f"La date saisie n'est pas valide !")
                return {"date": None}

# Classe de submit du formulaire; C'est dans cette classe (méthode run) que l'on va interroger l'API opendata.paris.fr 
# pour récupérer la liste des évenements en fonction des critères saisies
class ActionSubmit(Action):
    def name(self) -> Text:
        return "action_submit"
        
    def run(
        self,
        dispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Dict[Text, Any]]:    

        print("ActionSubmit")
        print(tracker.get_slot("evenement"))
        print(tracker.get_slot("prix"))
        print(tracker.get_slot("date"))

        categorie = tracker.get_slot("evenement") +'*' # récupération de la catégorie dans le slot
        prix = tracker.get_slot("prix") # récupération du prix dans le slot
        date = tracker.get_slot("date") # récupération de la date dans le slot
        date_saisie = datetime.strptime(date, "%d/%m/%Y").strftime("%Y/%m/%d") # formatage de la date

        # Initialisation des différents éléments qui vont constituer notre URL/requête
        url_paris = "opendata.paris.fr"
        url_appel = "/api/v2/catalog/datasets/que-faire-a-paris-/exports/json?" # nom du dataset à interroger : que-faire-a-paris-
        critere_categorie = "where=category%20like%20%20%22" + categorie # critère de catégorie
        critere_prix = "%22%20AND%20price_type%20like%20%20%22" + prix # critère de prix
        critere_dates ="%22%20AND%20(date_start%20%3E=%20'" + date_saisie + "'%20AND%20date_start%20%3C=%20'" + date_saisie+ "')" # critère de date
        critere_fin = "&limit=-1&pretty=false&timezone=UTC&accept=application/json" # nombre de résultat, time zone, et réponse en JSON
        api_key = "x-api-key=911359e10817e5337f705ae76afb68bdeab6a419f0923370e6d26a80" # api_key pour se connecter à l'API
        
        # Constitution de l'URL avec les différents critères (catégorie, prix, dates, UTC, api_key)
        if (prix == "Indifférent") :
            url_appel += critere_categorie + critere_dates + critere_fin + "&" + api_key # requête sans prix
        else :
            url_appel += critere_categorie + critere_prix + critere_dates + critere_fin + "&" + api_key # requête avec prix

        conn = http.client.HTTPSConnection(url_paris) # utilisation d'un HTTP client (standard de python) pour se connecter
        payload = ''
        headers = {}
        conn.request("GET", url_appel, payload, headers) # requête avec les différents paramètres
        res = conn.getresponse()
        list_event = json.loads(res.read().decode("utf-8")) # lecture du JSON de la réponse et stockage dans une liste

        if(len(list_event) == 0) : 
            # si la liste est vide, affichage d'un message
            dispatcher.utter_message(text=f"Aucun évènement(s) pour les critères recherchés.")
        else : 
            # si la liste est non vide, affichage du nombre d'évènements et des évènements
            dispatcher.utter_message(text=f"Il y a {len(list_event)} évènement(s) correspondants à vos critères :")

            # si la liste est non vide, affichage des évènements
            for counter, evenement_ok in enumerate(list_event, 1):
                print(evenement_ok['title'] + " | " + evenement_ok['date_start'] + " | " + evenement_ok['url'])
                date_ev = dateutil.parser.parse(evenement_ok['date_start'])
                dispatcher.utter_message(text = str(counter) + ") " + evenement_ok['title'] + " | " + date_ev.strftime('%d/%m/%Y %H:%M') + " | " + evenement_ok['price_type'] + " | " + evenement_ok['url'])
        dispatcher.utter_message(text=f"Voulez-vous encore autre chose ?")