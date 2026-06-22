package ma.transport.ms3localisation.repository;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import ma.transport.ms3localisation.entity.PositionGPS;
import ma.transport.ms3localisation.entity.PositionGPS.TypeCible;

public interface PositionGPSRepository extends JpaRepository<PositionGPS, Long> {

    /** Dernière position connue d'une cible */
    Optional<PositionGPS> findTopByCibleTypeAndCibleIdOrderByHorodatageDesc(
            TypeCible cibleType, Long cibleId);

    /** Historique d'une cible (les N dernières) */
    List<PositionGPS> findByCibleTypeAndCibleIdOrderByHorodatageDesc(
            TypeCible cibleType, Long cibleId);

    /** Toutes les dernières positions de tous les bus */
    @Query("""
        SELECT p FROM PositionGPS p
        WHERE p.cibleType = 'BUS'
          AND p.horodatage = (
              SELECT MAX(p2.horodatage)
              FROM PositionGPS p2
              WHERE p2.cibleType = 'BUS' AND p2.cibleId = p.cibleId
          )
        """)
    List<PositionGPS> findDernieresPositionsBus();

    /** Positions dans un intervalle de temps */
    List<PositionGPS> findByCibleTypeAndCibleIdAndHorodatageAfter(
            TypeCible cibleType, Long cibleId, LocalDateTime depuis);

    /** Nombre de positions enregistrées pour une cible */
    long countByCibleTypeAndCibleId(TypeCible cibleType, Long cibleId);

    /** Suppression des positions plus vieilles que X jours (purge) */
    void deleteByHorodatageBefore(@Param("date") LocalDateTime date);
}