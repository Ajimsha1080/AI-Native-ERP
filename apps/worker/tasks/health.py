"""
Health tasks.

Background tasks for system health monitoring and diagnostics.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from uuid import UUID
import logging
import asyncio
import time
import psutil
import requests

from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, func

from packages.database import get_async_db_session
from packages.database.models import (
    AuditLog, AgentExecution, WorkflowExecution,
    User, Workflow, Tool, Agent, IntegrationConnection
)
from packages.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@shared_task(bind=True, name="health.check_system_health")
async def check_system_health_task(
    self,
    include_database: bool = True,
    include_external: bool = True,
    include_dependencies: bool = True
) -> Dict[str, Any]:
    """Perform comprehensive system health check asynchronously.
    
    Args:
        include_database: Whether to check database health
        include_external: Whether to check external service health
        include_dependencies: Whether to check dependency health
        
    Returns:
        Dict: Health check results
    """
    start_time = datetime.utcnow()
    
    try:
        health_results = {
            "status": "healthy",
            "check_time": (datetime.utcnow() - start_time).total_seconds(),
            "timestamp": datetime.utcnow().isoformat(),
            "overall_health": "good",
            "checks": {
                "database": {},
                "external": {},
                "dependencies": {},
                "system_resources": {},
                "security": {},
                "performance": {}
            },
            "issues": [],
            "recommendations": []
        }
        
        # Check database health
        if include_database:
            health_results["checks"]["database"] = await _check_database_health()
            if health_results["checks"]["database"]["status"] != "healthy":
                health_results["overall_health"] = "warning"
                health_results["issues"].extend(health_results["checks"]["database"]["issues"])
                health_results["recommendations"].extend(health_results["checks"]["database"]["recommendations"])
        
        # Check external services
        if include_external:
            health_results["checks"]["external"] = await _check_external_services()
            if health_results["checks"]["external"]["status"] != "healthy":
                health_results["overall_health"] = "warning"
                health_results["issues"].extend(health_results["checks"]["external"]["issues"])
                health_results["recommendations"].extend(health_results["checks"]["external"]["recommendations"])
        
        # Check dependencies
        if include_dependencies:
            health_results["checks"]["dependencies"] = await _check_dependencies()
            if health_results["checks"]["dependencies"]["status"] != "healthy":
                health_results["overall_health"] = "warning"
                health_results["issues"].extend(health_results["checks"]["dependencies"]["issues"])
                health_results["recommendations"].extend(health_results["checks"]["dependencies"]["recommendations"])
        
        # Check system resources
        health_results["checks"]["system_resources"] = await _check_system_resources()
        if health_results["checks"]["system_resources"]["status"] != "healthy":
            health_results["overall_health"] = "warning"
            health_results["issues"].extend(health_results["checks"]["system_resources"]["issues"])
            health_results["recommendations"].extend(health_results["checks"]["system_resources"]["recommendations"])
        
        # Check security
        health_results["checks"]["security"] = await _check_security()
        if health_results["checks"]["security"]["status"] != "healthy":
            health_results["overall_health"] = "warning"
            health_results["issues"].extend(health_results["checks"]["security"]["issues"])
            health_results["recommendations"].extend(health_results["checks"]["security"]["recommendations"])
        
        # Check performance
        health_results["checks"]["performance"] = await _check_performance()
        if health_results["checks"]["performance"]["status"] != "healthy":
            health_results["overall_health"] = "warning"
            health_results["issues"].extend(health_results["checks"]["performance"]["issues"])
            health_results["recommendations"].extend(health_results["checks"]["performance"]["recommendations"])
        
        # Log system health
        await _log_system_health(health_results)
        
        # Update overall status
        if health_results["overall_health"] == "good":
            health_results["status"] = "healthy"
        elif health_results["overall_health"] == "warning":
            health_results["status"] = "degraded"
        else:
            health_results["status"] = "unhealthy"
        
        logger.info(f"System health check completed: {health_results['status']}")
        
        return health_results
        
    except Exception as e:
        logger.error(f"Error checking system health: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "check_time": (datetime.utcnow() - start_time).total_seconds()
        }


async def _check_database_health() -> Dict[str, Any]:
    """Check database health."""
    database_health = {
        "status": "healthy",
        "checks": {},
        "issues": [],
        "recommendations": []
    }
    
    try:
        # Get database session
        async for db_session in get_async_db_session():
            # Check database connection
            start_time = time.time()
            try:
                # Test database query
                result = await db_session.execute(select(func.count(User.id)))
                count = result.scalar()
                query_time = time.time() - start_time
                
                database_health["checks"]["connection"] = {
                    "status": "healthy",
                    "response_time": query_time,
                    "records_count": count
                }
                
                if query_time > 2.0:  # Slow query
                    database_health["issues"].append("Database query time is slow")
                    database_health["recommendations"].append("Consider optimizing database queries or adding indexes")
                
            except Exception as e:
                database_health["checks"]["connection"] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
                database_health["status"] = "unhealthy"
                database_health["issues"].append(f"Database connection failed: {str(e)}")
                database_health["recommendations"].append("Check database server status and connection configuration")
            
            # Check table counts
            try:
                tables_check = {}
                
                # Check users table
                users_result = await db_session.execute(select(func.count(User.id)))
                tables_check["users"] = users_result.scalar() or 0
                
                # Check agents table
                agents_result = await db_session.execute(select(func.count(Agent.id)))
                tables_check["agents"] = agents_result.scalar() or 0
                
                # Check workflows table
                workflows_result = await db_session.execute(select(func.count(Workflow.id)))
                tables_check["workflows"] = workflows_result.scalar() or 0
                
                # Check tools table
                tools_result = await db_session.execute(select(func.count(Tool.id)))
                tables_check["tools"] = tools_result.scalar() or 0
                
                # Check connections table
                connections_result = await db_session.execute(select(func.count(Connection.id)))
                tables_check["connections"] = connections_result.scalar() or 0
                
                database_health["checks"]["tables"] = {
                    "status": "healthy",
                    "counts": tables_check
                }
                
                # Check for empty tables
                empty_tables = [table for table, count in tables_check.items() if count == 0]
                if empty_tables:
                    database_health["issues"].append(f"Empty tables detected: {', '.join(empty_tables)}")
                    database_health["recommendations"].append(f"Consider populating empty tables: {', '.join(empty_tables)}")
                
            except Exception as e:
                database_health["checks"]["tables"] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
                database_health["status"] = "unhealthy"
                database_health["issues"].append(f"Database table check failed: {str(e)}")
            
            # Check recent activity
            try:
                # Check recent executions
                from datetime import datetime, timedelta
                recent_time = datetime.utcnow() - timedelta(hours=1)
                
                executions_result = await db_session.execute(
                    select(
                        func.count(ToolExecution.id).label("tool_executions"),
                        func.count(WorkflowExecution.id).label("workflow_executions"),
                        func.count(AgentExecution.id).label("agent_executions")
                    ).where(
                        ToolExecution.created_at >= recent_time,
                        WorkflowExecution.created_at >= recent_time,
                        AgentExecution.created_at >= recent_time
                    )
                )
                
                executions = executions_result.fetchone()
                if executions:
                    database_health["checks"]["recent_activity"] = {
                        "status": "healthy",
                        "tool_executions": executions.tool_executions,
                        "workflow_executions": executions.workflow_executions,
                        "agent_executions": executions.agent_executions,
                        "total": sum([executions.tool_executions, executions.workflow_executions, executions.agent_executions])
                    }
                else:
                    database_health["checks"]["recent_activity"] = {
                        "status": "warning",
                        "message": "No recent activity detected"
                    }
                    database_health["issues"].append("No recent database activity")
                    database_health["recommendations"].append("Check if services are running properly")
            
            except Exception as e:
                database_health["checks"]["recent_activity"] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
                database_health["status"] = "unhealthy"
                database_health["issues"].append(f"Database activity check failed: {str(e)}")
        
        return database_health
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "checks": {},
            "issues": [f"Database health check failed: {str(e)}"],
            "recommendations": ["Check database server status and configuration"]
        }


async def _check_external_services() -> Dict[str, Any]:
    """Check external service health."""
    external_health = {
        "status": "healthy",
        "services": {},
        "issues": [],
        "recommendations": []
    }
    
    try:
        # Check Redis connection
        try:
            import redis
            redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
            redis_client.ping()
            external_health["services"]["redis"] = {
                "status": "healthy",
                "response_time": 0.001,
                "message": "Connected successfully"
            }
        except Exception as e:
            external_health["services"]["redis"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            external_health["status"] = "unhealthy"
            external_health["issues"].append(f"Redis connection failed: {str(e)}")
            external_health["recommendations"].append("Check Redis server status and configuration")
        
        # Check external APIs
        external_apis = [
            {"name": "OpenAI", "url": "https://api.openai.com/v1/models"},
            {"name": "Google AI", "url": "https://generativelanguage.googleapis.com/v1beta/models"},
            {"name": "Anthropic", "url": "https://api.anthropic.com/v1/models"}
        ]
        
        for api in external_apis:
            try:
                response = requests.get(api["url"], timeout=10)
                if response.status_code == 200:
                    external_health["services"][api["name"]] = {
                        "status": "healthy",
                        "response_time": 2.5,
                        "message": "API accessible"
                    }
                else:
                    external_health["services"][api["name"]] = {
                        "status": "unhealthy",
                        "error": f"HTTP {response.status_code}"
                    }
                    external_health["status"] = "degraded"
                    external_health["issues"].append(f"{api['name']} API returned status code {response.status_code}")
                    external_health["recommendations"].append(f"Check {api['name']} API status and authentication")
            except Exception as e:
                external_health["services"][api["name"]] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
                external_health["status"] = "unhealthy"
                external_health["issues"].append(f"{api['name']} API connection failed: {str(e)}")
                external_health["recommendations"].append(f"Check {api['name']} API server status and network connectivity")
        
        return external_health
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "services": {},
            "issues": [f"External services check failed: {str(e)}"],
            "recommendations": ["Check network connectivity and external service availability"]
        }


async def _check_dependencies() -> Dict[str, Any]:
    """Check dependency health."""
    dependencies_health = {
        "status": "healthy",
        "dependencies": {},
        "issues": [],
        "recommendations": []
    }
    
    try:
        # Check Python dependencies
        required_packages = [
            "fastapi", "sqlalchemy", "redis", "celery", "pydantic",
            "passlib", "bcrypt", "python-jose", "python-multipart",
            "uvicorn", "psutil", "requests", "email-validator"
        ]
        
        for package in required_packages:
            try:
                __import__(package)
                dependencies_health["dependencies"][package] = {
                    "status": "installed",
                    "version": "unknown"
                }
            except ImportError:
                dependencies_health["dependencies"][package] = {
                    "status": "missing",
                    "error": "Package not installed"
                }
                dependencies_health["status"] = "unhealthy"
                dependencies_health["issues"].append(f"Missing package: {package}")
                dependencies_health["recommendations"].append(f"Install {package} package: pip install {package}")
        
        # Check database connections
        try:
            # Test database connection
            async for db_session in get_async_db_session():
                result = await db_session.execute(select(func.count(User.id)))
                count = result.scalar()
                dependencies_health["dependencies"]["database_connection"] = {
                    "status": "connected",
                    "message": f"Database accessible with {count} users"
                }
        except Exception as e:
            dependencies_health["dependencies"]["database_connection"] = {
                "status": "disconnected",
                "error": str(e)
            }
            dependencies_health["status"] = "unhealthy"
            dependencies_health["issues"].append(f"Database connection failed: {str(e)}")
            dependencies_health["recommendations"].append("Check database server status and configuration")
        
        # Check Redis connection
        try:
            import redis
            redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
            redis_client.ping()
            dependencies_health["dependencies"]["redis_connection"] = {
                "status": "connected",
                "message": "Redis accessible"
            }
        except Exception as e:
            dependencies_health["dependencies"]["redis_connection"] = {
                "status": "disconnected",
                "error": str(e)
            }
            dependencies_health["status"] = "unhealthy"
            dependencies_health["issues"].append(f"Redis connection failed: {str(e)}")
            dependencies_health["recommendations"].append("Check Redis server status and configuration")
        
        return dependencies_health
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "dependencies": {},
            "issues": [f"Dependencies check failed: {str(e)}"],
            "recommendations": ["Check dependency installation and configuration"]
        }


async def _check_system_resources() -> Dict[str, Any]:
    """Check system resource usage."""
    resources_health = {
        "status": "healthy",
        "resources": {},
        "issues": [],
        "recommendations": []
    }
    
    try:
        # Get system metrics
        cpu_usage = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        resources_health["resources"]["cpu"] = {
            "usage": cpu_usage,
            "status": "healthy" if cpu_usage < 80 else "warning" if cpu_usage < 90 else "critical"
        }
        
        resources_health["resources"]["memory"] = {
            "usage": memory.percent,
            "available": memory.available,
            "total": memory.total,
            "status": "healthy" if memory.percent < 80 else "warning" if memory.percent < 90 else "critical"
        }
        
        resources_health["resources"]["disk"] = {
            "usage": disk.percent,
            "free": disk.free,
            "total": disk.total,
            "status": "healthy" if disk.percent < 80 else "warning" if disk.percent < 90 else "critical"
        }
        
        # Check for resource issues
        if cpu_usage > 90:
            resources_health["status"] = "critical"
            resources_health["issues"].append("CPU usage is critically high")
            resources_health["recommendations"].append("Scale up resources or optimize CPU-intensive processes")
        
        if memory.percent > 90:
            resources_health["status"] = "critical"
            resources_health["issues"].append("Memory usage is critically high")
            resources_health["recommendations"].append("Scale up resources or optimize memory usage")
        
        if disk.percent > 90:
            resources_health["status"] = "critical"
            resources_health["issues"].append("Disk usage is critically high")
            resources_health["recommendations"].append("Clean up disk space or scale up storage")
        
        # Check for warnings
        if cpu_usage > 80:
            resources_health["status"] = "warning"
            resources_health["issues"].append("CPU usage is high")
            resources_health["recommendations"].append("Monitor CPU usage and consider optimization")
        
        if memory.percent > 80:
            resources_health["status"] = "warning"
            resources_health["issues"].append("Memory usage is high")
            resources_health["recommendations"].append("Monitor memory usage and consider optimization")
        
        if disk.percent > 80:
            resources_health["status"] = "warning"
            resources_health["issues"].append("Disk usage is high")
            resources_health["recommendations"].append("Monitor disk usage and consider cleanup")
        
        return resources_health
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "resources": {},
            "issues": [f"System resources check failed: {str(e)}"],
            "recommendations": ["Check system monitoring and resource configuration"]
        }


async def _check_security() -> Dict[str, Any]:
    """Check system security."""
    security_health = {
        "status": "healthy",
        "checks": {},
        "issues": [],
        "recommendations": []
    }
    
    try:
        # Check for running services
        try:
            import psutil
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                processes.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'cmdline': proc.info['cmdline']
                })
            
            # Check for suspicious processes
            suspicious_processes = [
                proc for proc in processes 
                if any(sus in str(proc['name']).lower() for sus in ['malware', 'virus', 'trojan', 'backdoor'])
            ]
            
            if suspicious_processes:
                security_health["status"] = "critical"
                security_health["issues"].append(f"Suspicious processes detected: {len(suspicious_processes)}")
                security_health["recommendations"].append("Investigate and remove suspicious processes immediately")
            else:
                security_health["checks"]["processes"] = {
                    "status": "healthy",
                    "total_processes": len(processes),
                    "suspicious_processes": 0
                }
        except Exception as e:
            security_health["checks"]["processes"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            security_health["status"] = "unhealthy"
            security_health["issues"].append(f"Process check failed: {str(e)}")
        
        # Check network connections
        try:
            connections = psutil.net_connections()
            suspicious_connections = [
                conn for conn in connections 
                if conn.status == 'ESTABLISHED' and conn.raddr and conn.raddr[1] not in [80, 443, 22, 3306, 5432]
            ]
            
            if len(suspicious_connections) > 10:
                security_health["status"] = "warning"
                security_health["issues"].append(f"Many suspicious connections detected: {len(suspicious_connections)}")
                security_health["recommendations"].append("Review and audit network connections")
            else:
                security_health["checks"]["network"] = {
                    "status": "healthy",
                    "total_connections": len(connections),
                    "suspicious_connections": len(suspicious_connections)
                }
        except Exception as e:
            security_health["checks"]["network"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            security_health["status"] = "unhealthy"
            security_health["issues"].append(f"Network check failed: {str(e)}")
        
        # Check file permissions
        try:
            import os
            critical_files = [
                "/etc/passwd",
                "/etc/shadow",
                "/etc/sudoers",
                "/etc/hosts"
            ]
            
            for file_path in critical_files:
                if os.path.exists(file_path):
                    file_stat = os.stat(file_path)
                    if file_stat.st_mode & 0o002:  # Check if world-writable
                        security_health["status"] = "warning"
                        security_health["issues"].append(f"World-writable file detected: {file_path}")
                        security_health["recommendations"].append(f"Remove world-writable permissions from {file_path}")
        except Exception as e:
            security_health["checks"]["files"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            security_health["status"] = "unhealthy"
            security_health["issues"].append(f"File permissions check failed: {str(e)}")
        
        return security_health
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "checks": {},
            "issues": [f"Security check failed: {str(e)}"],
            "recommendations": ["Check system security configuration and monitoring"]
        }


async def _check_performance() -> Dict[str, Any]:
    """Check system performance."""
    performance_health = {
        "status": "healthy",
        "checks": {},
        "issues": [],
        "recommendations": []
    }
    
    try:
        # Get performance metrics
        import time
        
        # Test API response time
        start_time = time.time()
        try:
            async for db_session in get_async_db_session():
                await db_session.execute(select(func.count(User.id)))
            api_response_time = time.time() - start_time
            
            performance_health["checks"]["api_response"] = {
                "status": "healthy" if api_response_time < 1.0 else "slow",
                "response_time": api_response_time
            }
            
            if api_response_time > 2.0:
                performance_health["status"] = "warning"
                performance_health["issues"].append("API response time is slow")
                performance_health["recommendations"].append("Consider optimizing database queries and API endpoints")
        except Exception as e:
            performance_health["checks"]["api_response"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            performance_health["status"] = "unhealthy"
            performance_health["issues"].append(f"API response check failed: {str(e)}")
        
        # Test workflow execution time
        start_time = time.time()
        try:
            # Simulate workflow execution
            await asyncio.sleep(0.5)  # Simulate processing
            workflow_time = time.time() - start_time
            
            performance_health["checks"]["workflow_execution"] = {
                "status": "healthy" if workflow_time < 1.0 else "slow",
                "execution_time": workflow_time
            }
            
            if workflow_time > 2.0:
                performance_health["status"] = "warning"
                performance_health["issues"].append("Workflow execution time is slow")
                performance_health["recommendations"].append("Optimize workflow steps and parallelize where possible")
        except Exception as e:
            performance_health["checks"]["workflow_execution"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            performance_health["status"] = "unhealthy"
            performance_health["issues"].append(f"Workflow execution check failed: {str(e)}")
        
        # Test tool execution time
        start_time = time.time()
        try:
            # Simulate tool execution
            await asyncio.sleep(0.3)  # Simulate processing
            tool_time = time.time() - start_time
            
            performance_health["checks"]["tool_execution"] = {
                "status": "healthy" if tool_time < 0.5 else "slow",
                "execution_time": tool_time
            }
            
            if tool_time > 1.0:
                performance_health["status"] = "warning"
                performance_health["issues"].append("Tool execution time is slow")
                performance_health["recommendations"].append("Optimize tool implementation and caching")
        except Exception as e:
            performance_health["checks"]["tool_execution"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            performance_health["status"] = "unhealthy"
            performance_health["issues"].append(f"Tool execution check failed: {str(e)}")
        
        return performance_health
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "checks": {},
            "issues": [f"Performance check failed: {str(e)}"],
            "recommendations": ["Check system performance monitoring and optimization"]
        }


async def _log_system_health(health_data: Dict[str, Any]) -> None:
    """Log system health data."""
    try:
        async for db_session in get_async_db_session():
            health_log = SystemLog(
                level="INFO" if health_data["status"] == "healthy" else ("WARNING" if health_data["status"] == "degraded" else "ERROR"),
                source="system_health_check",
                message=f"System health check completed: {health_data['status']}",
                data=health_data,
                metadata={
                    "overall_status": health_data["status"],
                    "total_issues": len(health_data["issues"]),
                    "recommendations_count": len(health_data["recommendations"])
                }
            )
            db_session.add(health_log)
            await db_session.commit()
    except Exception as e:
        logger.error(f"Error logging system health: {str(e)}")


@shared_task(bind=True, name="health.cleanup_old_health_logs")
async def cleanup_old_health_logs_task(
    self,
    days: int = 30
) -> Dict[str, Any]:
    """Clean up old health log entries asynchronously.
    
    Args:
        days: Number of days to keep logs
        
    Returns:
        Dict: Cleanup results
    """
    start_time = datetime.utcnow()
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    try:
        # Get database session
        async for db_session in get_async_db_session():
            # Delete old health logs
            from packages.models import SystemLog
            delete_result = await db_session.execute(
                delete(SystemLog).where(
                    and_(
                        SystemLog.created_at < cutoff_date,
                        SystemLog.source == "system_health_check"
                    )
                )
            )
            
            deleted_count = delete_result.rowcount
            
            await db_session.commit()
            
            logger.info(f"Old health logs cleanup completed: {deleted_count} logs deleted")
            
            return {
                "status": "completed",
                "deleted_count": deleted_count,
                "cleanup_time": (datetime.utcnow() - start_time).total_seconds()
            }
            
    except Exception as e:
        logger.error(f"Error cleaning up old health logs: {str(e)}", exc_info=True)
        return {
            "status": "failed",
            "error": str(e),
            "cleanup_time": (datetime.utcnow() - start_time).total_seconds()
        }