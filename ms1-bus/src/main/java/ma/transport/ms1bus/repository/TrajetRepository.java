package ma.transport.ms1bus.repository;

import java.util.List;
import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;

import ma.transport.ms1bus.entity.Trajet;
import ma.transport.ms1bus.entity.Trajet.StatutTrajet;

public interface TrajetRepository extends JpaRepository<Trajet, Long> {
    List<Trajet> findByStatutOrderByHeureDebutDesc(StatutTrajet statut);
    List<Trajet> findByChauffeurIdAndStatutOrderByHeureDebutDesc(Long chauffeurId, StatutTrajet statut);
    Optional<Trajet> findFirstByChauffeurIdAndStatut(Long chauffeurId, StatutTrajet statut);
    Optional<Trajet> findFirstByBusIdAndStatut(Long busId, StatutTrajet statut);
}
