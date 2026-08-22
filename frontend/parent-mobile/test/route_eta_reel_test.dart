import 'dart:convert';
import 'dart:io';

import 'package:parent_app/services/route_eta.dart';
import 'package:flutter_test/flutter_test.dart';

/// `route_eta` sur une **vraie** tournée MS5, pas sur une polyligne jouet.
///
/// La fixture `test/fixtures/tournee_groupe1.json` est la réponse réelle de
/// `POST /api/planification/tournee?groupeId=1&sens=matin` sur les données v2 :
/// 50 arrêts, 753 points OSRM, 17,2 km, 36 min. Les tests de `route_eta_test.dart`
/// valident la géométrie sur un carré de 4 points ; ceux-ci valident qu'elle tient
/// sur un circuit urbain réel, avec ses boucles et ses rues qui se frôlent — c'est
/// là que la projection d'un point sur une polyligne se trompe.
void main() {
  late RoutePolyline poly;
  late double distancePlanM;
  late double dureePlanMin;
  late List<Map<String, dynamic>> etapes;

  setUpAll(() {
    final brut = File('test/fixtures/tournee_groupe1.json').readAsStringSync();
    final j = jsonDecode(brut) as Map<String, dynamic>;
    poly = (j['geometrie'] as List)
        .map((p) => (p as List).map((c) => (c as num).toDouble()).toList())
        .toList();
    distancePlanM = (j['distance_m'] as num).toDouble();
    dureePlanMin = (j['duree_min'] as num).toDouble();
    etapes = (j['etapes'] as List)
        .map((e) => Map<String, dynamic>.from(e as Map))
        .toList();
  });

  test('Given la tournée réelle, Then la fixture est bien celle attendue', () {
    expect(poly.length, 753);
    expect(etapes.length, 50);
    expect(distancePlanM, closeTo(17241.1, 0.1));
    expect(dureePlanMin, closeTo(35.99, 0.01));
  });

  test('Given la polyligne et le total annoncé par MS5, '
      'Then les deux décrivent bien LE MÊME itinéraire', () {
    // Ce test était à l'origine un tripwire documentant un écart de +10,92 % :
    // `distance_m` venait de la matrice OSRM /table, tandis que `geometrie`
    // venait de /route appelé sans `continue_straight=false` — OSRM imposait
    // alors de franchir chaque waypoint tout droit et insérait des demi-tours.
    // Mesuré contre l'OSRM local sur les 52 waypoints réels :
    //     sans continue_straight : 19 123,5 m / 42,23 min / 882 points
    //     avec  (=false)         : 17 241,1 m / 35,99 min / 753 points
    //     matrice /table (réf.)  : 17 241,1 m / 35,99 min
    // MS5 corrigé (`osrm_client.py::geometrie`), les deux coïncident. Le test
    // garde donc la même valeur — mais assert désormais la CONVERGENCE, et
    // échouera si la régression revient.
    final mesure = longueurRoute(poly);
    final ecartPct = (mesure - distancePlanM).abs() / distancePlanM * 100;
    expect(
      ecartPct,
      lessThan(1),
      reason:
          'mesure=${mesure.toStringAsFixed(0)} m vs annoncé='
          '${distancePlanM.toStringAsFixed(0)} m — un écart de ~11 % signifie '
          'que `continue_straight=false` a disparu de MS5',
    );
  });

  test('Given la tournée corrigée, Then elle boucle TOUJOURS sur elle-même', () {
    // Le correctif MS5 supprime les demi-tours, mais pas la nature cyclique du
    // circuit : école → élèves → école. Le plancher de progression
    // (`depuisAlongM`) reste donc indispensable — ce test l'atteste.
    final ecart = distanceRestanteM(poly, poly.last[0], poly.last[1])!;
    expect(
      ecart,
      greaterThan(longueurRoute(poly) * 0.9),
      reason:
          'sans mémoire de progression, le terminus se recale sur le '
          'départ et « il reste tout le circuit »',
    );
  });

  test('Given un bus qui progresse sur toute la tournée, '
      'Then la distance restante décroît à CHAQUE point, sans exception', () {
    // Le bug d'origine (corrigé le 19/08) : un ETA visant l'école en distance
    // directe AUGMENTE pendant le ramassage. Ici on parcourt les 882 points
    // réels et on exige une décroissance stricte — sur un circuit qui repasse
    // près de l'école et se croise lui-même.
    double? precedent;
    var alongM = -1.0;
    var violations = 0;
    var pire = 0.0;

    for (var i = 0; i < poly.length; i += 5) {
      // On réinjecte l'abscisse atteinte, comme le fait l'écran de tournée.
      final inputs = etaInputsRestants(
        poly,
        poly[i][0],
        poly[i][1],
        dureePlanMin: dureePlanMin,
        depuisAlongM: alongM,
      );
      expect(inputs, isNotNull, reason: 'point $i');
      alongM = inputs!.alongM;
      final d = inputs.distanceM;
      if (precedent != null && d > precedent) {
        violations++;
        final delta = d - precedent;
        if (delta > pire) pire = delta;
      }
      precedent = d;
    }

    expect(
      violations,
      0,
      reason:
          'la distance restante a augmenté $violations fois '
          '(pire écart : ${pire.toStringAsFixed(1)} m) — '
          'c\'est exactement le symptôme du compte à rebours qui remonte',
    );
  });

  test('Given le bus au départ puis à l\'arrivée, '
      'Then il reste tout le circuit, puis presque rien', () {
    // Le circuit est un cycle FERMÉ (premier point == dernier, 0,0 m) : sans
    // mémoire de progression, la position d'arrivée se recale sur le DÉPART
    // et le reste repasse à 19 km. C'est le saut 1,5 min → 39 min observé sur
    // les données réelles. On rejoue donc le parcours pour arriver au bout
    // avec une abscisse acquise, comme en conditions réelles.
    final auDepart = distanceRestanteM(poly, poly.first[0], poly.first[1])!;
    expect(auDepart, closeTo(longueurRoute(poly), 50));

    var alongM = -1.0;
    double? reste;
    // `poly.length - 1` inclus : un pas de 5 s'arrêterait avant le dernier
    // point et laisserait une centaine de mètres non parcourus, ce qui ferait
    // échouer le test pour une raison qui n'a rien à voir avec le recalage.
    for (var i = 0; i < poly.length; i += 5) {
      final j = i + 5 >= poly.length ? poly.length - 1 : i;
      final inputs = etaInputsRestants(
        poly,
        poly[j][0],
        poly[j][1],
        dureePlanMin: dureePlanMin,
        depuisAlongM: alongM,
      )!;
      alongM = inputs.alongM;
      reste = inputs.distanceM;
    }
    expect(
      reste,
      lessThan(50),
      reason: "à l'arrivée le reste doit être quasi nul, pas 19 km",
    );
  });

  test('Given la vitesse déduite des totaux OSRM réels, '
      'Then elle est plausible pour une tournée urbaine', () {
    // `etaInputsRestants` dérive désormais la vitesse de la polyligne
    // mesurée, pas du total MS5 : au départ, l'ETA vaut exactement la durée
    // annoncée de la tournée (36 min), au lieu de 40 min (+11 %).
    final v = vitesseCircuitMs(longueurRoute(poly), dureePlanMin);
    expect(v * 3.6, inInclusiveRange(20, 45));

    final auDepart = etaInputsRestants(
      poly,
      poly.first[0],
      poly.first[1],
      dureePlanMin: dureePlanMin,
    )!;
    expect(
      auDepart.dureeBaseS / 60,
      closeTo(dureePlanMin, 0.1),
      reason: 'cohérence : reste total / vitesse == durée annoncée',
    );
  });

  test('Given un domicile d\'élève sur le circuit, '
      'Then la distance jusqu\'à lui décroît quand le bus s\'en approche', () {
    // On prend un point du circuit aux deux tiers comme « domicile » cible.
    final cible = poly[(poly.length * 0.66).round()];
    final mesures = <double>[];
    var alongM = -1.0;
    for (var i = 0; i < poly.length * 0.6; i += 40) {
      final inputs = etaInputsRestants(
        poly,
        poly[i][0],
        poly[i][1],
        cibleLat: cible[0],
        cibleLng: cible[1],
        dureePlanMin: dureePlanMin,
        depuisAlongM: alongM,
      );
      if (inputs == null) continue;
      alongM = inputs.alongM;
      mesures.add(inputs.distanceM);
    }

    expect(mesures.length, greaterThan(5));
    for (var i = 1; i < mesures.length; i++) {
      expect(
        mesures[i],
        lessThanOrEqualTo(mesures[i - 1] + 1),
        reason: 'mesure $i : ${mesures[i]} > ${mesures[i - 1]}',
      );
    }
    expect(mesures.last, lessThan(mesures.first));
  });

  test(
    'Given les cumuls MS5 des 50 arrêts, '
    'Then ils croissent et couvrent le circuit — base de l\'écran Prévisions',
    () {
      // L'écran ETA passe ces cumuls à MS12 comme distance/durée de base.
      // S'ils ne sont pas monotones, les heures de passage affichées reculent.
      for (var i = 1; i < etapes.length; i++) {
        expect(
          etapes[i]['cumul_duree_s'] as num,
          greaterThan(etapes[i - 1]['cumul_duree_s'] as num),
          reason: 'arrêt ${i + 1}',
        );
        expect(
          etapes[i]['cumul_distance_m'] as num,
          greaterThan(etapes[i - 1]['cumul_distance_m'] as num),
          reason: 'arrêt ${i + 1}',
        );
      }
      expect(etapes.first['rang'], 1);
      expect(etapes.last['rang'], 50);
      // Le dernier arrêt est atteint avant le retour à l'école.
      expect(
        (etapes.last['cumul_distance_m'] as num).toDouble(),
        lessThan(distancePlanM),
      );
    },
  );
}
