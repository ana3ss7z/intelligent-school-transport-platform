package ma.transport.ms10incidents.repository;

import ma.transport.ms10incidents.entity.Incident;
import ma.transport.ms10incidents.entity.Incident.StatutIncident;
import ma.transport.ms10incidents.entity.Incident.TypeIncident;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface IncidentRepository extends JpaRepository<Incident, Long> {

    List<Incident> findByBusIdOrderByDateSignalementDesc(Long busId);

    List<Incident> findByStatutOrderByDateSignalementDesc(StatutIncident statut);

    List<Incident> findByTypeOrderByDateSignalementDesc(TypeIncident type);

    List<Incident> findAllByOrderByDateSignalementDesc();

    List<Incident> findBySignaleParOrderByDateSignalementDesc(Long userId);

    long countByStatut(StatutIncident statut);
}
