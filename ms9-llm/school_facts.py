"""
Socle de connaissances « école » injecté dans le prompt système du parent.

Même mécanisme que `schema_prompt.SCHEMA` côté admin : une constante concaténée au prompt, pas de
recherche ni d'index. Le corpus visé (une page) tient largement dans la fenêtre de contexte ; ce qui
contraint le service est le **TPM** (8 000 jetons/minute), d'où le format compact.

⚠️ RÈGLE DE RÉDACTION — à respecter pour toute modification de ce fichier :
    on n'écrit ici QUE des faits vérifiables. Une valeur inventée qui paraît plausible est
    exactement le défaut que ce socle corrige : elle transformerait une hallucination du modèle
    en désinformation assumée par le service.

    · FONCTIONNEMENT : comportements réellement implémentés (vérifiables dans le code).
    · POLITIQUE : décisions propres à l'établissement. Tant qu'elles ne sont pas confirmées par
      l'administration, elles restent marquées « non renseigné » — le modèle renverra alors vers
      l'administration au lieu d'inventer. C'est le comportement voulu, pas un manque.
"""

VERSION_SOCLE = "2026-08-19"

FAITS_ECOLE = f"""
CONNAISSANCES ÉCOLE ET TRANSPORT (version {VERSION_SOCLE})
Seule source autorisée pour les questions générales sur l'école, le transport et les procédures.

ÉTABLISSEMENT
- École Al Massira, à Meknès. C'est la destination de tous les bus.

FONCTIONNEMENT DU TRANSPORT
- Le matin, le bus part de l'école, ramasse les élèves un par un, puis revient à l'école.
- Le soir, il repart de l'école et dépose les élèves dans le même ordre que le matin
  (choix d'équité : le temps passé à bord est ainsi le même à l'aller et au retour).
- Chaque élève a un ordre de passage fixe, calculé pour minimiser la durée de la tournée.

CE QUE L'APPLICATION FAIT AUTOMATIQUEMENT
- Une notification est envoyée au parent quand le bus est à environ 10 minutes.
- Une notification est envoyée quand l'enfant monte dans le bus, et quand il est déposé.
- Une notification est envoyée à l'arrivée du bus à l'école.
- La position du bus et l'heure d'arrivée estimée sont consultables en direct dans l'application.
- L'écran « Prévisions » donne l'heure de passage estimée pour chaque enfant.
- Les messages de l'administration et du chauffeur arrivent dans la messagerie de l'application.
  Cette messagerie est en RÉCEPTION SEULE : le parent ne peut pas y répondre.
- En cas d'incident sur le trajet, le chauffeur le signale et l'administration est prévenue ;
  le parent est notifié lorsque l'incident est résolu.

POLITIQUE DE L'ÉTABLISSEMENT — non renseigné à ce jour
Les points suivants n'ont pas encore été communiqués par l'administration. Pour chacun, indique au
parent que l'information n'est pas disponible dans l'application et invite-le à contacter
l'administration de l'école. N'avance JAMAIS d'horaire, de délai, de tarif ni de règle inventés :
- horaires officiels de départ et d'arrivée
- durée d'attente du bus à un arrêt
- procédure et délai pour signaler une absence
- conditions d'inscription au transport et tarifs
- règlement intérieur, objets oubliés, calendrier scolaire
- coordonnées de l'administration (téléphone, horaires d'accueil)
""".strip()
