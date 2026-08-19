import 'package:flutter_test/flutter_test.dart';
import 'package:parent_app/services/route_eta.dart';

/// Tournée jouet reproduisant la forme réelle d'un circuit MS5 : l'école est au DÉPART
/// et au RETOUR, le bus s'en éloigne pendant le ramassage.
///
///   école(0,0) → est jusqu'à (0, 0.02) → nord (0.01, 0.02) → retour école
/// Les points sont en degrés ; à cette latitude 0.001° ≈ 111 m.
const _ecole = [0.0, 0.0];
final RoutePolyline _tournee = [
  [0.0, 0.0], // école (départ)
  [0.0, 0.01], // arrêt A
  [0.0, 0.02], // arrêt B (le plus loin)
  [0.01, 0.02], // arrêt C
  [0.01, 0.0], // remontée
  [0.0, 0.0], // école (retour)
];

void main() {
  group('distanceRestanteM — cible = fin de tournée (école)', () {
    test('Given un bus qui progresse sur le circuit, '
        'When il s\'ÉLOIGNE de l\'école à vol d\'oiseau, '
        'Then la distance restante DÉCROÎT quand même', () {
      // Trois positions successives, de plus en plus loin de l'école en ligne droite.
      final d1 = distanceRestanteM(
        _tournee,
        0.0,
        0.005,
      )!; // début, proche école
      final d2 = distanceRestanteM(_tournee, 0.0, 0.015)!; // s'éloigne
      final d3 = distanceRestanteM(
        _tournee,
        0.01,
        0.02,
      )!; // le plus loin (arrêt C)

      // C'est tout l'objet du correctif : ces trois valeurs doivent décroître,
      // alors que la distance à vol d'oiseau vers l'école, elle, augmente.
      expect(d2, lessThan(d1));
      expect(d3, lessThan(d2));
    });

    test('Given le bus au terminus, Then il reste ~0 m', () {
      final reste = distanceRestanteM(_tournee, _ecole[0], _ecole[1])!;
      // Le point école se projette aussi sur le départ ; on vérifie que la fin est atteinte
      // depuis la toute dernière portion du circuit.
      final resteFin = distanceRestanteM(_tournee, 0.001, 0.0)!;
      expect(resteFin, lessThan(400));
      expect(reste, greaterThanOrEqualTo(0));
    });

    test(
      'Given une polyligne vide ou dégénérée, Then null (repli point-à-point)',
      () {
        expect(distanceRestanteM(const [], 0, 0), isNull);
        expect(
          distanceRestanteM(
            const [
              [0.0, 0.0],
            ],
            0,
            0,
          ),
          isNull,
        );
      },
    );
  });

  group('distanceRestanteM — cible = domicile d\'un élève', () {
    test(
      'Given un domicile DEVANT le bus, '
      'Then la distance restante est celle du parcours restant jusqu\'à lui',
      () {
        // Bus juste après l'école ; domicile = arrêt B, à ~0.02° d'arc vers l'est.
        final d = distanceRestanteM(
          _tournee,
          0.0,
          0.002,
          cibleLat: 0.0,
          cibleLng: 0.02,
        )!;
        // ≈ (0.02 - 0.002) degrés ≈ 2 km
        expect(d, greaterThan(1800));
        expect(d, lessThan(2200));
      },
    );

    test('Given le bus qui se rapproche du domicile, '
        'Then la distance restante décroît', () {
      final loin = distanceRestanteM(
        _tournee,
        0.0,
        0.002,
        cibleLat: 0.0,
        cibleLng: 0.02,
      )!;
      final proche = distanceRestanteM(
        _tournee,
        0.0,
        0.018,
        cibleLat: 0.0,
        cibleLng: 0.02,
      )!;
      expect(proche, lessThan(loin));
    });

    test('Given un domicile DÉJÀ DÉPASSÉ par le bus, '
        'Then on ne renvoie pas une distance négative', () {
      final d = distanceRestanteM(
        _tournee,
        0.01,
        0.02,
        cibleLat: 0.0,
        cibleLng: 0.01,
      )!;
      expect(d, greaterThanOrEqualTo(0));
    });
  });

  group('vitesseCircuitMs', () {
    test(
      'Given les totaux OSRM, Then la vitesse moyenne du circuit en est déduite',
      () {
        // 12 000 m en 20 min = 10 m/s
        expect(vitesseCircuitMs(12000, 20), closeTo(10, 0.01));
      },
    );

    test(
      'Given des totaux absents, Then repli sur la vitesse urbaine par défaut',
      () {
        expect(vitesseCircuitMs(null, null), 7);
        expect(vitesseCircuitMs(0, 0), 7);
      },
    );

    test('Given un ratio aberrant, Then la vitesse est bornée', () {
      expect(
        vitesseCircuitMs(100000, 1),
        lessThanOrEqualTo(22),
      ); // 1667 m/s → borné
      expect(
        vitesseCircuitMs(10, 60),
        greaterThanOrEqualTo(2.5),
      ); // quasi nul → borné
    });
  });

  group('etaInputsRestants', () {
    test(
      'Given une tournée et une vitesse, Then durée = distance / vitesse',
      () {
        final r = etaInputsRestants(
          _tournee,
          0.0,
          0.0,
          distancePlanM: 6000,
          dureePlanMin: 10, // 10 m/s
        )!;
        expect(r.dureeBaseS, closeTo(r.distanceM / 10, 0.01));
      },
    );

    test('Given une polyligne inexploitable, Then null', () {
      expect(etaInputsRestants(const [], 0, 0), isNull);
    });
  });
}
