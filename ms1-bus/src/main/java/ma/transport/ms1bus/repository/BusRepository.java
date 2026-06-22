package ma.transport.ms1bus.repository;

import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;

import ma.transport.ms1bus.entity.Bus;
import ma.transport.ms1bus.enums.StatutBus;

public interface BusRepository extends JpaRepository<Bus, Long> {
    List<Bus> findByStatut(StatutBus statut);
    boolean existsByMatricule(String matricule);
    List<Bus> findByChauffeurId(Long chauffeurId);
}